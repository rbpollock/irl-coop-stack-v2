# Backup and restore

**Status: working and verified — 2026-10-12.** First backup: snapshot `ba67f908`, 282 MiB,
11 seconds, off-host on surfy. First restore drill: **passed** (239/239 tables, 33 roles,
26/26 secrets, git bundle readable).

Scripts: `infra/scripts/backup.sh` · `infra/scripts/restore-drill.sh`.
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
   `restic -r sftp:service@surfy:/home/service/irl-backup/restic restore latest --target /tmp/r`
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

## 7. Known gaps — stated, not hidden

| Gap | Status |
|---|---|
| **Same-site, not offsite** | surfy is on this LAN. Offsite (a third copy elsewhere, or an encrypted object-store target) is unbuilt |
| **The destination is surfy's home, not the 3.4 TB USB** | `/mnt/usb` is root-owned on surfy, so `service` cannot write there. One command on surfy fixes it: `sudo mkdir -p /mnt/usb/irl-backup && sudo chown service:service /mnt/usb/irl-backup`, then move the repository and point `RESTIC_REPOSITORY` at it |
| **The password has no password-manager copy** | §3 — the one item that makes recovery assume a surviving machine |
| **No automated verification of the *restore*** | the drill is scheduled, but nothing alerts on failure yet |
| **The archive is not itself group-held** | the restic password and the destination are one person's. This is exactly the §2.1 precondition in `group-operated-stack.md` |