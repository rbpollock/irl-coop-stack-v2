# Privileged helpers — the NOPASSWD grant, and why it is shaped this way

**Status: mechanism written 2026-10-13; not yet installed (installing needs the owner's
password, which is the point).**

## Why

Three separate tasks tonight ended at a password prompt: moving Docker's data-root, the kubo
upgrade, and anything else that touches `/etc` or a systemd unit. The work stops, the person
becomes the mechanism, and privileged maintenance simply doesn't happen unattended.

The alternative is to give the agent a *narrow, auditable* grant — installed deliberately,
revocable in one command — rather than letting it accumulate either broad sudo or none.

## The property that makes it safe

**A sudoers rule is only as narrow as the thing it grants.**

```
service ALL=(root) NOPASSWD: /home/service/.../infra/scripts/*.sh     # ← UNCONDITIONAL ROOT
```

That line looks scoped and is not. Those scripts live in a directory the granted account
**owns and can edit**, so the grant is really "run anything at all as root, any time": replace
a script, run it, done. Wildcards make it worse.

So the grant is for **running** programs the account **cannot change**:

| | |
|---|---|
| Where | `/usr/local/sbin/irl-coop/` — **owned `root:root`, mode 0755** |
| Which | explicit file paths, **no wildcards** |
| Permission | `service` may **execute** them as root |
| Updating them | requires the **owner's password** — that is the security property, not a limitation |
| Revoking | `rm /etc/sudoers.d/irl-coop` — immediately effective |

The repo copies stay user-owned and freely editable; they are the source of truth. The
*installed* copies are what carries the grant, and only root can replace them.

## What is granted today

Exactly one program:

- `move-docker-dataroot.sh` — moves Docker's data-root to the secondary disk. ⚠ This host
  uses the containerd snapshotter (driver `overlayfs`): the images live in `/var/lib/containerd`
  (~134.7 GB), not `/var/lib/docker` (~2.3 GB, a metadata stub). The script's header and its
  `image` directory check both warn on this now; it would otherwise take the whole stack down to
  move 2.3 GB. The load-bearing get south: the disk problem on this box was fixed by the image
  prune (70 GB → / to 47%), not by moving anything.

That list is deliberately short, and adding to it needs the password. **Anything that does not
genuinely need root stays out**: `rebalance-to-secondary.sh`, `backup.sh`, `backup-ipfs.sh`,
`golden-images.sh` and `restore-drill.sh` all run as the user (the caches and the model dirs are
in the user's own home; the backup scripts use the docker group). They are not here because
they do not need to be.

## Install / update / revoke

```sh
sudo bash infra/scripts/install-privileged-helpers.sh   # install or update
sudo -l -U service                                      # see what is granted
rm /etc/sudoers.d/irl-coop                              # revoke (instant)
```

The installer validates the rule with `visudo -cf` **before** putting it in place — a malformed
file in `/etc/sudoers.d/` can lock `sudo` out entirely, so it is written to a temp file, checked,
and only then installed at mode 0440.

## The honest risks, stated rather than implied

1. **This is root-equivalent for the `service` account**, channelled through those specific
   programs. If a granted script is buggy or does something destructive, it does so as root.
   The mitigation is that the *set* is one file, it is readable, and adding to it needs the
   password.
2. **No `requiretty` handling is needed here.** The installer first tried
   `Defaults:service !requiretty` and `visudo` rejected the whole file with
   `unknown setting: 'requiretty'` — this sudo build does not have it, so there is no TTY
   requirement to relax. The failure was harmless *because* the installer validates before
   installing: had it written the file first, `/etc/sudoers.d/` would have been unparseable
   and `sudo` unusable. Non-interactive `NOPASSWD` works without any extra Defaults.
3. **The agent's own command-approval gate remains**, so this grant does not mean unattended
   execution — it means a privileged command can be *approved* rather than *handed over*.
4. **Granted scripts should be argument-free or hardcoded.** `sudo` with NOPASSWD resets the
   environment by default, and a rule without `SETENV` refuses `sudo -E`, so environment
   injection into a granted script is not available — but a script that trusts its *arguments*
   would be a hole regardless. Keep them dumb.
5. **Run it yourself and this is all unnecessary.** The grant exists to remove a bottleneck,
   not to remove your ability to do the work by hand — and if you would rather keep privileged
   operations entirely manual, delete the sudoers file and nothing else changes.

## Relationship to the rest of the stack's design

This is the same question the stack asks everywhere else — *who holds the privileged path* —
applied to the host itself. It is a documented, narrow, revocable concentration, recorded here
rather than left as an implicit convenience. The group-operated doctrine in
`group-operated-stack.md` §2.2 says the same thing about host root: **the hand is fine; the
unilateral hand is not.** Today the hand is one account plus one sudoers file.