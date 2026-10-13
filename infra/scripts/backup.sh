#!/usr/bin/env bash
# Backup the irl.coop stack to an off-host restic repository.
#
# Design notes (see docs/BACKUP.md):
#   - Tier 1 = the irreplaceable set: every database, the secrets, the .env files,
#     the certs, the instance tree, and a git bundle. Tens of MB to ~1 GB.
#   - Tier 2 = the object store (MinIO buckets), mirrored per bucket.
#   - Tier 3 = REBUILDABLE and deliberately NOT backed up: model weights
#     (fetch-model.sh), the PMTiles basemap + Noto glyphs under geo-data/
#     (build scripts), and the container images (built from Dockerfiles).
#     Backing these up would multiply the archive for zero recovery value.
#   - The restic repository is encrypted client-side, so the destination host
#     never sees plaintext. The repository password is therefore the single
#     point of failure for the whole archive: escrow it off this host
#     (docs/BACKUP.md §"The password").
#
# Usage:  infra/scripts/backup.sh [--dry-run] [--no-minio] [--no-prune]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
INSTANCE="${INSTANCE:-dev}"

RESTIC_REPOSITORY="${RESTIC_REPOSITORY:-sftp:service@surfy:/mnt/usb/irl-backup/restic}"
RESTIC_PASSWORD_FILE="${RESTIC_PASSWORD_FILE:-$ROOT/infra/instances/$INSTANCE/secrets/backup-restic-pass}"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/id_ed25519_surfy}"
STAGING="${STAGING:-/mnt/storage/backup-staging}"
LOGDIR="$ROOT/.logs"
LOGFILE="$LOGDIR/backup.log"

PG_CONTAINER="${PG_CONTAINER:-storage-postgres-1}"
PG_SUPERUSER="${PG_SUPERUSER:-irlcoop}"
MINIO_CONTAINER="${MINIO_CONTAINER:-storage-minio-1}"
MINIO_BUCKETS="${MINIO_BUCKETS:-docs stalwart matrix-media plane}"
KEEP_DAILY="${KEEP_DAILY:-7}"; KEEP_WEEKLY="${KEEP_WEEKLY:-4}"; KEEP_MONTHLY="${KEEP_MONTHLY:-6}"

DRY_RUN=""; DO_MINIO=1; DO_PRUNE=1
for a in "$@"; do
  case "$a" in
    --dry-run) DRY_RUN="--dry-run";;
    --no-minio) DO_MINIO=0;;
    --no-prune) DO_PRUNE=0;;
    *) echo "unknown flag: $a" >&2; exit 2;;
  esac
done

mkdir -p "$LOGDIR"
log() { printf '%s  %s\n' "$(date -Is)" "$*" | tee -a "$LOGFILE"; }
die() { log "FATAL: $*"; exit 1; }

export RESTIC_REPOSITORY RESTIC_PASSWORD_FILE
# restic shells out to plain `ssh`; the destination key lives in ~/.ssh/config
# as `Host surfy` (IdentityFile), so the sftp: URL needs no extra options.

log "=== backup start (instance=$INSTANCE, repo=$RESTIC_REPOSITORY) ==="

# ── preflight ────────────────────────────────────────────────────────────────
[ -r "$RESTIC_PASSWORD_FILE" ] || die "restic password file missing/unreadable: $RESTIC_PASSWORD_FILE"
command -v restic >/dev/null || die "restic not installed"
docker inspect "$PG_CONTAINER" >/dev/null 2>&1 || die "postgres container not running: $PG_CONTAINER"
if ! restic cat config >/dev/null 2>&1; then
  log "no repository at destination — initializing"
  restic init || die "restic init failed (destination reachable and writable?)"
fi
DEST_FREE="$(ssh -o BatchMode=yes surfy 'df -h /home | tail -1' 2>/dev/null || echo 'unknown')"
log "destination /home: $DEST_FREE"

# ── stage ────────────────────────────────────────────────────────────────────
rm -rf "$STAGING"; mkdir -p "$STAGING"/{db,etc,minio}
cd "$ROOT"

log "dumping cluster globals (roles/grants)…"
docker exec "$PG_CONTAINER" pg_dumpall -U "$PG_SUPERUSER" --roles-only \
  | zstd -T0 -q -6 -o "$STAGING/db/00-roles.sql.zst" \
  || die "roles dump failed"

log "dumping each database (custom format)…"
mapfile -t DBS < <(docker exec "$PG_CONTAINER" psql -U "$PG_SUPERUSER" -Atc \
  "select datname from pg_database where not datistemplate and datname <> 'postgres' order by 1")
for db in "${DBS[@]}"; do
  printf '%s' "$db" | grep -qE '^[A-Za-z0-9_]+$' || { log "skipping odd db name: $db"; continue; }
  if docker exec "$PG_CONTAINER" pg_dump -U "$PG_SUPERUSER" -Fc -f "/tmp/$db.dump" "$db" 2>>"$LOGFILE"; then
    docker cp "$PG_CONTAINER:/tmp/$db.dump" "$STAGING/db/$db.dump" >/dev/null
    docker exec "$PG_CONTAINER" rm -f "/tmp/$db.dump"
    log "  $db  $(du -h "$STAGING/db/$db.dump" | cut -f1)"
  else
    log "  $db  DUMP FAILED (see $LOGFILE)"
  fi
done

if [ "$DO_MINIO" = 1 ]; then
  log "mirroring MinIO buckets…"
  for b in $MINIO_BUCKETS; do
    if docker exec "$MINIO_CONTAINER" mc ls "local/$b" >/dev/null 2>&1; then
      rm -rf "$STAGING/minio/$b"
      docker exec "$MINIO_CONTAINER" rm -rf "/tmp/backup/$b" >/dev/null 2>&1 || true
      docker exec "$MINIO_CONTAINER" mc mirror --overwrite --quiet "local/$b" "/tmp/backup/$b" >/dev/null 2>&1 \
        && docker cp "$MINIO_CONTAINER:/tmp/backup/$b" "$STAGING/minio/$b" >/dev/null \
        && log "  $b  $(du -sh "$STAGING/minio/$b" | cut -f1)" \
        || log "  $b  MIRROR FAILED"
      docker exec "$MINIO_CONTAINER" rm -rf "/tmp/backup/$b" >/dev/null 2>&1 || true
    else
      log "  $b  ABSENT (skipped)"
    fi
  done
else
  log "minio skipped (--no-minio)"
fi

log "staging the secret set and configuration…"
# the tiny set that makes recovery possible at all
mkdir -p "$STAGING/etc/secrets"
cp -a "infra/instances/$INSTANCE/secrets/." "$STAGING/etc/secrets/" 2>/dev/null || true
[ -d "infra/instances/$INSTANCE/certs" ] && cp -a "infra/instances/$INSTANCE/certs" "$STAGING/etc/certs" || log "  no certs dir"
# generated derived secrets + resolved host-app env (the file coop-api reads)
[ -r "infra/out/$INSTANCE/secrets.env" ] && cp -a "infra/out/$INSTANCE/secrets.env" "$STAGING/etc/secrets.env"
for f in apps/coop-api/.env apps/web/irl-dashboard/.env.local apps/web/starter-kit/.env.local; do
  [ -r "$f" ] && { mkdir -p "$STAGING/etc/env/$(dirname "$f")"; cp -a "$f" "$STAGING/etc/env/$f"; }
done
# ansible vault (committable ciphertext, but keep it with the rest)
[ -r infra/ansible/inventory/group_vars/all/vault.yml ] && \
  cp -a infra/ansible/inventory/group_vars/all/vault.yml "$STAGING/etc/"
# the declarative source of truth (configuration only — data/ is root-owned runtime
# state; the databases and objects in it are captured above, logically)
mkdir -p "$STAGING/etc/instances"
tar -C "infra/instances" -cf - --exclude="data" --exclude="secrets" --exclude="certs" \
  --ignore-failed-read "$INSTANCE" 2>>"$LOGFILE" | tar -C "$STAGING/etc/instances" -xf - \
  || log "  WARNING: some instance-tree paths were unreadable (see $LOGFILE)"

# Root-owned runtime secrets (gitignored, so the repo cannot restore them). These need
# sudo. If it is unavailable the gap is LOGGED loudly, never silently dropped — an
# invisible hole in a backup is worse than a known one.
# config/matrix, etc/coturn and config/element-call are owned by this account (readable
# directly, captured by the tar above). The signing key is owned by the container's uid
# (mode 0640) and is NOT readable from here — it is captured through the container that
# owns it, which avoids needing sudo for the backup at all.
mkdir -p "$STAGING/etc/container-secrets"
MATRIX_CONTAINER="${MATRIX_CONTAINER:-$(docker ps --format '{{.Names}}' | grep -iE 'synapse|matrix' | head -1)}"
if [ -n "$MATRIX_CONTAINER" ]; then
  KEYS="$(docker exec "$MATRIX_CONTAINER" sh -c 'ls /data/*.signing.key 2>/dev/null' || true)"
  if [ -n "$KEYS" ]; then
    for k in $KEYS; do
      if docker exec "$MATRIX_CONTAINER" cat "$k" > "$STAGING/etc/container-secrets/$(basename "$k")" 2>>"$LOGFILE"; then
        log "  signing key: $k (via $MATRIX_CONTAINER)"
      else
        log "  WARNING: could not read $k"
      fi
    done
  else
    log "  note: no *.signing.key found inside $MATRIX_CONTAINER"
  fi
else
  log "  WARNING: no synapse container found — the Matrix signing key is NOT captured"
fi
# belt-and-braces: the whole committed repo as one file (survives losing GitHub)
log "writing git bundle…"
git bundle create "$STAGING/etc/repo.bundle" --all >/dev/null 2>&1 || log "  git bundle failed"
# the escrow copy of the restic password, so the archive is recoverable without this host
cp -a "$RESTIC_PASSWORD_FILE" "$STAGING/etc/backup-restic-pass"
chmod 600 "$STAGING/etc/backup-restic-pass"

log "staged: $(du -sh "$STAGING" | cut -f1) total"
du -sh "$STAGING"/* | sed 's/^/  /' | tee -a "$LOGFILE"

# ── back up ──────────────────────────────────────────────────────────────────
log "restic backup…"
restic backup "$STAGING" \
  --tag "irl-coop-$INSTANCE" --host "$(hostname)" --exclude-caches \
  $DRY_RUN 2>&1 | tee -a "$LOGFILE" | tail -4

if [ "$DO_PRUNE" = 1 ] && [ -z "$DRY_RUN" ]; then
  log "forget --prune (daily=$KEEP_DAILY weekly=$KEEP_WEEKLY monthly=$KEEP_MONTHLY)…"
  restic forget --tag "irl-coop-$INSTANCE" \
    --keep-daily "$KEEP_DAILY" --keep-weekly "$KEEP_WEEKLY" --keep-monthly "$KEEP_MONTHLY" \
    --prune 2>&1 | tee -a "$LOGFILE" | tail -3
fi

log "=== snapshots ==="
restic snapshots --compact 2>&1 | tee -a "$LOGFILE" | tail -8
log "=== backup complete ==="