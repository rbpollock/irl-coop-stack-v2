# Backup and restore

**Status: working and verified — 2026-10-12.** First backup: snapshot `ba67f908`, 282 MiB,
11 seconds, off-host on surfy. First restore drill: **passed** (239/239 tables, 33 roles,
26/26 secrets, git bundle readable).

Scripts: `infra/scripts/backup.sh` · `infra/scripts/restore-drill.sh`.
Destination: **surfy `/mnt/usb/irl-backup/restic`** (the 3.6 TB drive, 3% used).
Logs: `.logs/backup.log` · `.logs/restore-drill.log`.

## 1. What this is, and what it is not

An **encrypted, deduplicating, off-host copy of the irreplaceable data**, plus a script
that proves it can be restored. `restic` encrypts client-side, so the destination host
never sees plaintext.

**It is a second copy on the same site, not offsite.** surfy (`192.168.18.11`) is on the
same LAN as this host (`192.168.18.20`). This covers the failures that actually happen —
this machine's disk dying, a bad upgrade, accidental deletion, theft of *this* machine.
It does **not** cover fire, flood, or a break-in that takes the premises. Offsite is a
separate, later tier (§7).

## 2. The tiers — and why the archive is only 282 MiB

The whole point of the tiering is that most of the stack's bulk has **zero recovery
value**, because it is rebuildable from source. Backing it up would multiply the archive
without making recovery more possible.

| Tier | Contents | Size | Why |
|---|---|---|---|
| **1 — irreplaceable** | every database (custom-format dumps, 19 of them), cluster roles/grants, `infra/instances/dev/secrets/`, `infra/out/dev/secrets.env`, the app `.env` files, the ACME certs, the ansible vault, the instance tree (config only), a `git bundle --all` of the repo, the Matrix signing key | **~284 MiB** | Nothing here can be re-derived. The repositories, tokens and signing material are the stack |
| **2 — the object store** | MinIO buckets `docs`, `stalwart`, `matrix-media`, `plane` (mirrored per bucket) | ~22 MiB | Real uploaded content — documents, mail blobs, chat media |
| **3 — deliberately NOT backed up** | model weights (`fetch-model.sh`), the PMTiles basemap + Noto glyphs under `geo-data/` (23 GB, build scripts), container images (built from Dockerfiles), `node_modules` | 23 GB+ | Rebuildable or re-downloadable. Included in the archive they would dominate it and buy nothing |
| **3e — the named EXCEPTIONS** | images that are **not** rebuildable, saved as golden artifacts (`infra/scripts/golden-images.sh` → `golden/` in the archive) | ~478 MB | Tier 3 says images are rebuildable. For the images where that is false, saying nothing is the bug: the exceptions are written down, saved, and carried into the archive by `backup.sh` |

**Current golden set (2026-10-13):** `irlcoop/nocodb-gate-sso:2026.08.3` (the runtime base the
NocoDB fork's `Dockerfile.irlcoop` FROMs — a local-only tag) and `:2026.08.12` (deployed, and the
only home of the compiled nc-gui frontend). Rationale and measurements:
`docs/IMAGE-PROVENANCE.md` §6.3.

## 3. The password — the single point of failure

`infra/instances/dev/secrets/backup-restic-pass` (0600, gitignored) unlocks the archive.
**Lose it and the backup is unrecoverable** — restic says so at init, and it is not
exaggerating.

Three copies exist, deliberately:
1. the file on this host (for the automation to run unattended);
2. a copy **inside the archive itself** (`etc/backup-restic-pass`) — which sounds
   circular and is not: it is what makes the archive self-describing once you can open it;
3. the file is also on surfy alongside the repository.

**What is missing is the copy that survives losing this host *and* surfy: put it in your
password manager.** Until that exists, recovery assumes at least one of the two machines
survives. This is also, precisely, a group-vault item (§2.1 of
`docs/design/group-operated-stack.md`) — a secret whose loss is unrecoverable and whose
custody is currently one person's.

## 4. Running it

```bash
infra/scripts/backup.sh              # dump → stage → restic backup → forget --prune
infra/scripts/backup.sh --dry-run    # stage and report, write no snapshot
infra/scripts/backup.sh --no-minio   # skip the object store
infra/scripts/restore-drill.sh       # restore the latest snapshot and verify it
```

Scheduled: a daily backup and a weekly drill (§6). Retention: 7 daily, 4 weekly,
6 monthly, pruned on every run.

## 5. The drill — why it exists

**A backup that has never been restored is a hypothesis.** The drill restores the most
recent snapshot, then checks that the artifact actually works:

- the roles dump decompresses and yields its `CREATE ROLE` statements;
- one real database is `pg_restore`d into a throwaway database (`irlcoop_restore_drill`)
  and its table count is compared against live — then the scratch database is dropped;
- the `git bundle` lists refs (so the repo survives losing GitHub as well as the disk);
- the restored secret set matches the live one file-for-file.

It touches nothing that matters: one disposable database and one temporary directory.

## 6. Restoring for real (the procedure)

1. Get the restic password (§3 — password manager, or the copy on surfy).
2. On a machine with `restic` and the ssh key:
   `restic -r sftp:service@surfy:/mnt/usb/irl-backup/restic restore latest --target /tmp/r`
3. Databases: for each file in `/tmp/r/.../db/`, restore with
   `docker exec -i storage-postgres-1 pg_restore -U irlcoop -d <db> --no-owner` (custom
   format), or `psql -f` after `zstd -d` for the roles dump. Create the role/DB set from
   `00-roles.sql` first — RLS depends on the roles existing.
4. Secrets and config: copy `/tmp/r/.../etc/secrets/` back to `infra/instances/dev/secrets/`,
   `etc/env/` back to the app paths, `etc/instances/` over `infra/instances/`.
5. Objects: `docker exec storage-minio-1 mc mirror /tmp/... local/<bucket>` per bucket, or
   upload with `mc cp`.
6. Regenerate the stack (`generator.py dev`) and bring it up (`stack-up.sh`) — the
   code comes from the repo, not the archive.

**Recovery does not need the archive for the code.** The repository is on GitHub as well;
the archive's copy exists for the case where the reproducible path is also gone.

## 7. The offsite tier — IPFS (137.184.24.48)

surfy's USB is on this LAN: it survives a dead disk, a bad upgrade, a stolen machine — not
fire, flood or a break-in. The IPFS node on **`137.184.24.48` is a DigitalOcean box**, so it
is a genuinely different failure domain, and it is the first offsite copy the stack has had.

`infra/scripts/backup-ipfs.sh`, in ~14 seconds once warm:

1. `restic copy` our repository (on surfy) into a local mirror at `/mnt/storage/restic-mirror`
   — incremental and integrity-checked, and it leaves a third local copy as a side effect.
2. `rsync` the mirror to `irlbackup@137.184.24.48:/home/irlbackup/restic`. restic pack files
   are immutable, so only new packs move.
3. `ipfs add -r` there and pin the result. IPFS dedups identical blocks, so only new blocks
   are stored.
4. Pin the **new** root, then unpin the previous one — the node holds roughly one copy of the
   current repository, not a growing pile of historical roots.
5. Record the CID in `infra/backup-cids.json`, which is committed. **That file is the proof:**
   anyone with a CID can fetch and re-pin it, so the offsite copy is something the group can
   hold rather than something that depends on one person's server.

**Verified 2026-10-13.** Root CID `QmW59SZGnMbYemKLdYHzECZzhEoR5AYT9FDCCkMhdnTELa`, pinned,
served by the public gateway, and **the restore drill passed against the fetched-back copy**:
239/239 tables, 33 roles, 26/26 secrets, git bundle readable.

### What to know about that node — read before touching it

| | |
|---|---|
| **`ipfs repo gc` is not forbidden — it is the node owner's maintenance step, and it is needed.** | `gc` deletes only **unpinned** blocks, so pinned content (the ~2,550 recursive pins, including the book collection) is untouched. But every restic prune leaves our superseded packs unreachable-and-stored, and only `gc` reclaims them: without a periodic collect on that node, our mirror slowly fills it with dead weight. So the rule is **we do not run it silently** (it may also drop someone's unpinned work) — the owner runs it deliberately, and it is safe for everything pinned. An earlier note in this file said "never run gc"; that was too broad and would have let the node fill up |
| **Capacity is real** | `StorageMax` is 10 GB and the repo sits at **~69%** (6.6 GB). Ours is ~400 MB and the pin-new-then-unpin-old rule keeps it flat. The script warns past 80% |
| **The account is `irlbackup`** | Key-only (`passwd -l`), and the key is restricted with `from="64.135.141.73,192.168.18.20,100.122.136.95"` so a copy is useless off this host. It needs **no sudo** — it never touches the IPFS repo directory, only the daemon's local API |
| **It drives the daemon with `--api`, not `IPFS_API`** | `IPFS_API` does not work on kubo 0.12 — the CLI still looks for a repo in `$HOME/.ipfs`. `ipfs --api /ip4/127.0.0.1/tcp/5001 …` does |
| **Do not trust `ipfs add` output order to find the root** | `-q` prints a line per file and `-Q` is unreliable for directories on 0.12 with concurrent workers; a pack-file CID resolves fine and looks healthy. The script identifies the root **by its links** (`config`, `data`, `index`, `keys`, `snapshots`) and refuses to record anything else |
| **kubo 0.12.0 is from 2022 and faces the internet** | End-of-life, with years of CVEs since. A real security item: upgrade it. Related: `PasswordAuthentication` is still `yes` and `PermitRootLogin yes` on that box — do **not** turn those off until you have installed your own key, or you will lock yourself out |
| **A public gateway means world-readable ciphertext** | Fine, because restic encrypts client-side — but the rule is absolute: **only ever pin encrypted material there.** Anyone with a CID can read and enumerate the bytes |

### Restoring from IPFS

Fetch the repository by CID (rsync from the box, or walk it through the gateway), then it is
an ordinary restic repository:

```sh
rsync -a -e ssh irlbackup@137.184.24.48:/home/irlbackup/restic/ /tmp/from-ipfs/
restic -r /tmp/from-ipfs snapshots          # needs the password, §3
RESTIC_REPOSITORY=/tmp/from-ipfs infra/scripts/restore-drill.sh
```

## 8. Known gaps — stated, not hidden

| Gap | Status |
|---|---|
| ~~**Same-site, not offsite**~~ | **CLOSED 2026-10-13** by the IPFS tier (§7) — a DigitalOcean box, offsite, verified by a passing drill. The surfy copy remains same-site, and that is fine: it is the fast, cheap, always-available second copy |
| **One node is one copy** | The IPFS copy lives on a single server with a single operator. It becomes durable when a second node — or a member — also pins the CID. The CID list is published so that is possible |
| **The password has no password-manager copy** | §3 — the one item that makes recovery assume a surviving machine |
| **No automated verification of the *restore*** | the drill is scheduled, but nothing alerts on failure yet |
| **The archive is not itself group-held** | the restic password and the destination are one person's. This is exactly the §2.1 precondition in `group-operated-stack.md` |