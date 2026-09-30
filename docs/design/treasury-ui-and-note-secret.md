# Treasury on-screen — the note vault, the split, and what stays private

Status: design · Sep 2026 · Builds on the *live* treasury seam (`apps/treasury-relayer`:
`POST /notes`, `GET /notes`, the note-tree, off-chain Groth16 gate + pool submit),
and the treasury view slot in platform-views.md §2/§5 (§6.2–5). Companion docs:
private-treasury-guards-ledgers.md (the ledger model), money-in-and-out.md,
group-home.md (the screens this drops into).

## 0. The one non-negotiable

**The note vault is PRIVATE per member, not a group balance.** A note is a UTXO:
`{secret, amount, commitment, nullifier}`. Its commitment is public in the tree,
but who holds it, what it's worth, and when it moves are private. So the treasury UI
is NOT a collective "here's how much we have" dashboard — that number does not
exist publicly. The only things a treasury screen may truthfully show:

- **my notes** — the commitments, amounts, and secrets of the notes **I** hold
  (my personal private wallet, opened with my own key/session),
- **the pool root** — the aggregate public fact (proof activity: a commitment root
  changed), **not** balances.
- **policy/gates** — the guard rules (quorum, limits, split) that bind the Safe;
  those are public and matter to a member deciding whether to contribute.

Anything that renders "the group has $X in the treasury" is, by construction, a lie
in this model — unless the group has explicitly opened selective disclosure (a
project viewing key, tax/compliance reporting; §3).

This is the UI truth that shapes everything below: the treasury view is two
surfaces — a **personal vault** (member-scoped) and a **shared policy/audit**
surface. They are not the same pane and must not be merged.

## 1. The two surfaces

### 1.1 The personal vault (private, member-scoped)

The member sees only notes whose secret they can open. Opened with the member's
session key (the "per-" seat) — coop-api resolves the app.sub role and hands back
only this member's notes.

What it shows, per note: last-4 of the commitment, the amount, spent/unspent
state, the **action**: spend, share-as-proof, export-secret. The note's secret is
shown ONCE on mint (the "here is your private receipt — keep it" screen, below)
and never again; the list shows a reveal-inline only when the member explicitly
chooses to re-reveal.

Actions are Temporal signals (platform-views.md §3), not direct writes.

### 1.2 The collective policy + audit surface (public)

- the **pool root** (the live Poseidon root) + a small "recent proof activity"
  feed — root changes, not balances; this is the "Now" pulse of the treasury.
- the **guard conditions** (limits, quorum, encumbrances) — authoritative and
  public.
- **selective-disclosure controls** if a policy chose them (which project/amount to
  reveal to whom, one at a time).

The two are a single platform `treasury` view with two panes — but the privacy
boundary is the one invariant no widget crosses.

## 2. The flows (mapped to the live seam)

### Mint a note (fund the vault)
1. Member: "Add funds" — enters amount, picks direction (fiat card → escrow, or
   direct deposit—fundraising-programmable-transfers.md).
2. coop-api → `POST /notes {amount}` on the relayer → returns the NOTE **with its
   secret**.
3. UI: **the one-time secret reveal.** "Here is your private note. Copy it, or
   store it in your vault. We don't keep it" — *the relayer does keep it today (dev);
   the real keeper must NOT* — it's the single disposable secret. This is the
   non-negotiable honest copy.

### Spend/redeem (the payment)
1. Select one-or-more unspent notes (or "note" = the whole vault for a single amount).
2. The client builds the spend proof (secret, root, path) — done in-app eventually;
   today the relayer has the tree, so proof-fetch is `POST /notes/:index/spend`
   (contains-tree + prepare) then `/relay` (verify).
3. UI: "You are spending N from your vault into [recipient 's tree / outbound
   transfer]. Confirm." — never a double-tap surprise; the outbound endpoint is a
   guarded Temporal signal.

## 3. The "did the pool accept it?" feedback loop

Because the pool adopt a root and seal a nullifier, the spend is DETERMINISTIC and
CHECKABLE: after relay+submit the UI observes `root` changed and the note flip to
`spent`. That is the one "did it happen" that's real — the root transition, not a
wish. Surface it as a small "proof accepted, tree moved" toast, not a fake
"balance reconciled."

## 4. Pipeline in the view system

- `treasury` layout: `{panes: ['vault','policy'], rootFeed: bool}` — extends the union.
- render: Webstudio (as before). read: RLS-scoped (the vault = app.sub-scoped
  notes; the policy = public data). act: Temporal signals → the seams already built
  (relayer /notes + /relay + submit.ts).
- **`vault` pane source:** a NEW read, not a table: coop-api/project → relayer
  `GET /notes` filtered to the caller — decoupled from NocoDB entirely (secrets
  never enter RLS tables).

## 5. Honest status

- live now: the relayer note seam (`POST /notes`, `GET /notes`, `GET /notes/:index'),
  the tree (root deterministic), the proof gate, the submit seam.
- NOT built: any UI pane, coop-api session-gating of notes, proof-provision mining,
  persistence of the secret (today the relayer keeps it — a dev compromise; the
  design doesn't let that become the production state).

## 6. Open decision (worth a session)

**Where does the member's secret really live?**

1. **Relayer-only (today):** simplest but the relayer becomes the weak point —
   it holds all secrets. Fine for prototype, wrong for production.
2. **Session-key encryption:** pick a per-member viewing key; the secret is
   encrypted at rest (in the ledger) with the member's public key, so the relayer
   holds ciphertext, never plaintext; the UI/decryption happens in the member's
   session. Stronger; needs a member key store + key rotation story.
3. **Only-shown-once, then yours:** the relayer mints the note (needs the secret to
   compute the commitment) then DELETES the plaintext (keep only the ciphertext /
   commitment). The member is the only true holder — the TM 'here-keep-this'
   pattern. Cleanest privacy, hardest UX (lost secret = lost note, no recovery).

Preference (this model): **2 as launched default, 3 optional (a "self-custody note"
sticker).** But it's a real decision — worth a dedicated doc + design pass, not a
side-churn. The treasury vault UI above works for all three (it only ever renders
the member's own notes; how they're stored is the difference).