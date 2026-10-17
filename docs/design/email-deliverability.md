# Email deliverability — why irl.coop mail lands in the Gmail spam folder, and the fix

**One line.** The domain has no DKIM signature, DMARC is `p=none` and relaxed, SPF is a
soft-fail, and — decisively — mail leaves from a **residential / dynamic IP** instead of a
sender-shaped one.

The good news: it is *not* on the common blocklists, so this is a reputation-and-identity
gap, not a fired-list. Fixable in a weekend of DNS + one config change, plus a planned
move of egress.

## What I audited (Oct 2026)

| Signal | Current value | Verdict |
|---|---|---|
| DKIM | none (`_s1._domainkey`, no signing) | **missing** |
| SPF | `v=spf1 mx ~all` | soft-fail, only MX |
| DMARC | `v=DMARC1; p=none; adkim=r; aspf=r` | no enforcement, relaxed alignment |
| Egress IP / rDNS | `64.135..73` → PTR `…dyn.me-south.gonetspeed.com` | **decisive negative** |
| Blocklist status | Spamhaus Zen (`zen`), SpamCop, Barracuda — **clean** | recoverable |

The mail stack: MTA **Stalwart** (`communication-stalwart-1`, + optional 587 submission with
OAuth2 coop-JWT), config lives in Postgres (the `config.json` in
`infra/instances/dev/data/stalwart/etc/` is only the datastore pointer). Outbound goes out
of this host's own `64.135.141.73` — a gonetspeed residential/dynamic block.

Gmail's model is simple: **did the message pass identity (DKIM/SPF/DMARC alignment), and does
the IP look like a real one?** Here both halves are weak → spam.

## Step 1 — publish identity records (DNS operator)

**DKIM** — sign irl.coop. The key is already generated (private:
`infra/instances/dev/secrets/mail/dkim-s1-private.pem`, 0600, gitignored). Its public half is
committed so you can cut‑and‑paste the record:
`infra/instances/dev/mail-dkim-s1-public.txt`. The value to publish:

```
_s1._domainkey.irl.coop  TXT  "v=DKIM1; k=rsa; p=<contents of infra/instances/dev/mail-dkim-s1-public.txt>"
```

**SPF** — keep `mx` (MX = this IP) but enforce instead of soft-fail:

```
irl.coop  TXT  "v=spf1 mx -all"
```

**DMARC** — enforce (quarantine, not reject until proven), keep reports:

```
_dmarc.irl.coop  TXT  "v=DMARC1; p=quarantine; rua=mailto:admin@irl.coop; adkim=s; aspf=r; pct=100"
```

**rDNS / PTR** is owned by the *ISP*, so it can only be fixed by switching which address
egresses (Step 3). You can't turn the home PTR into `mail.irl.coop`.

## Step 2 — turn on DKIM signing in the MTA

Stalwart signs on outbound. Its config is DB backed, so this is an admin‑API change, not a
file edit. Use the `s1` private key above as the signing secret for the `irl.coop` domain,
selector `s1`. Validate before and after with a `mail-tester`-style check to that same IP
(toolbox / recipient across **multiple** providers, not just partners).

## Step 3 — the decisive fix: egress

The identity records (steps 1–2) make each message *verifiable*; they do not make the
**home IP** pass as a sender. A residential/dynamic address cannot carry transactional
reputation to Gmail. Three options:

- **A. Self‑hosted outbound VPS (recommended for irl.coop).** A small always‑on server with a
  static IP whose rDNS is set to `mail.irl.coop`; Stalwart runs there as the outbound MTA
  (this host keeps the store). Warm up 2–4 weeks low volume. Cost: a few $/month. Keeps the
  sovereign, self‑hosted posture and matches the existing DNS‑DIRECT/vault pattern.
- **B. Transactional ESP (Resend / Postmark / SES).** Their warmed IPs reach Gmail inbox
  instantly; add their DKIM selector. Fastest path to a demo; but the identity hands over to
  the ESP — the opposite of what the coop is, so only good as a bridge.
- **C. Keep sending from here** — the current state; it's how the mail already lands in spam.

**Recommendation:** do Steps 1–2 now (free, reversible, and right regardless).
Start a **VPS (A)** in parallel so the first invitations land inbox before a pilot. Use the
ESP (B) only if pilot invites must be in the mailbox before the VPS IP warms.

**Applied (live since 2026-10-17):** DKIM keypair generated (private stored + ignored); all
three DNS records **published through the in-repo Gandi LiveDNS v5 key** and verified live
(apex SPF `mx -all`, `_dmarc` `p=quarantine`, `_s1._domainkey` DKIM) on Gandi + public
resolvers. So Step 1 is done — no DNS operator action remains.

**Remaining for the owner / admin:** (2) flip Stalwart's DKIM signing on (private `s1` key,
admin API) and (3) choose the egress route (A self-hosted outbound VPS recommended, B
ESP-bridge). And a hygiene item: the Gandi v5 API key is **committed** in
`infra/scripts/renew-cert.sh` — rotate it in the Gandi console and move it to the gitignored
`secrets/` tree.