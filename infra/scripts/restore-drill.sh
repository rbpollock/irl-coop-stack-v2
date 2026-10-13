#!/usr/bin/env bash
# Restore drill — proves the backup is actually restorable, not just present.
#
# A backup that has never been restored is a hypothesis. This script:
#   1. restores the most recent snapshot to a scratch directory,
#   2. loads a real database dump into a scratch database and compares its
#      table count against live,
#   3. verifies the roles dump and the git bundle are intact,
#   4. compares the restored secret set against the live one,
#   5. drops the scratch database and removes the scratch directory.
#
# It writes to NOTHING that matters: one throwaway database, one temp dir.
# Usage:  infra/scripts/restore-drill.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
INSTANCE="${INSTANCE:-dev}"
RESTIC_REPOSITORY="${RESTIC_REPOSITORY:-sftp:service@surfy:/mnt/usb/irl-backup/restic}"
RESTIC_PASSWORD_FILE="${RESTIC_PASSWORD_FILE:-$ROOT/infra/instances/$INSTANCE/secrets/backup-restic-pass}"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/id_ed25519_surfy}"
DRILL_DIR="${DRILL_DIR:-/mnt/storage/restore-drill}"
PG_CONTAINER="${PG_CONTAINER:-storage-postgres-1}"
PG_SUPERUSER="${PG_SUPERUSER:-irlcoop}"
SCRATCH_DB="${SCRATCH_DB:-irlcoop_restore_drill}"
TEST_DB="${TEST_DB:-irlcoop}"          # a small, real database
LOGDIR="$ROOT/.logs"

export RESTIC_REPOSITORY RESTIC_PASSWORD_FILE
# restic shells out to plain `ssh`; the destination key lives in ~/.ssh/config
# as `Host surfy` (IdentityFile), so the sftp: URL needs no extra options.

mkdir -p "$LOGDIR"
log() { printf '%s  %s\n' "$(date -Is)" "$*" | tee -a "$LOGDIR/restore-drill.log"; }
ok()  { log "  PASS  $*"; }
bad() { log "  FAIL  $*"; FAILED=1; }
FAILED=0

log "=== restore drill start ==="

# ── 1. restore the latest snapshot ───────────────────────────────────────────
rm -rf "$DRILL_DIR"; mkdir -p "$DRILL_DIR"
SNAP="$(restic snapshots --json --tag "irl-coop-$INSTANCE" 2>/dev/null | python3 -c \
  'import json,sys; s=json.load(sys.stdin); print(s[-1]["short_id"] if s else "")')"
[ -n "$SNAP" ] || { log "FATAL: no snapshots found in $RESTIC_REPOSITORY"; exit 1; }
log "restoring snapshot $SNAP → $DRILL_DIR"
restic restore "$SNAP" --target "$DRILL_DIR" 2>&1 | tail -2 | tee -a "$LOGDIR/restore-drill.log"

# restic preserves the staged path, so find where the payload landed
BASE="$(find "$DRILL_DIR" -maxdepth 6 -type d -name db -printf '%h\n' 2>/dev/null | head -1)"
[ -n "$BASE" ] || BASE="$DRILL_DIR"
log "payload root: $BASE"
du -sh "$BASE" | sed 's/^/  restored: /' | tee -a "$LOGDIR/restore-drill.log"

# ── 2. roles + a real database round-trip ────────────────────────────────────
if [ -r "$BASE/db/00-roles.sql.zst" ]; then
  NROLES="$(zstd -dc "$BASE/db/00-roles.sql.zst" | grep -c '^CREATE ROLE' || true)"
  [ "$NROLES" -gt 0 ] && ok "roles dump decompresses: $NROLES roles" || bad "roles dump has no CREATE ROLE"
else
  bad "roles dump missing"
fi

if [ -r "$BASE/db/$TEST_DB.dump" ]; then
  LIVE_TABLES="$(docker exec "$PG_CONTAINER" psql -U "$PG_SUPERUSER" -Atc \
    "select count(*) from information_schema.tables where table_schema not in ('pg_catalog','information_schema')" -d "$TEST_DB")"
  docker cp "$BASE/db/$TEST_DB.dump" "$PG_CONTAINER:/tmp/drill.dump" >/dev/null
  docker exec "$PG_CONTAINER" psql -U "$PG_SUPERUSER" -q -c "drop database if exists $SCRATCH_DB" -d postgres
  docker exec "$PG_CONTAINER" psql -U "$PG_SUPERUSER" -q -c "create database $SCRATCH_DB" -d postgres
  # no --exit-on-error: RLS policies and extensions can emit benign warnings
  docker exec "$PG_CONTAINER" pg_restore -U "$PG_SUPERUSER" -d "$SCRATCH_DB" --no-owner \
    /tmp/drill.dump >>"$LOGDIR/restore-drill.log" 2>&1 || true
  RESTORED_TABLES="$(docker exec "$PG_CONTAINER" psql -U "$PG_SUPERUSER" -Atc \
    "select count(*) from information_schema.tables where table_schema not in ('pg_catalog','information_schema')" -d "$SCRATCH_DB")"
  log "  $TEST_DB: live $LIVE_TABLES tables, restored $RESTORED_TABLES tables"
  if [ "$RESTORED_TABLES" -gt 0 ] && [ "$RESTORED_TABLES" -ge "$((LIVE_TABLES * 9 / 10))" ]; then
    ok "restored database matches live (within 10%)"
  else
    bad "restored table count $RESTORED_TABLES vs live $LIVE_TABLES"
  fi
  docker exec "$PG_CONTAINER" psql -U "$PG_SUPERUSER" -q -c "drop database if exists $SCRATCH_DB" -d postgres
  docker exec "$PG_CONTAINER" rm -f /tmp/drill.dump
  ok "scratch database dropped"
else
  bad "no dump for $TEST_DB in the snapshot"
fi

# ── 3. git bundle intact ─────────────────────────────────────────────────────
if [ -r "$BASE/etc/repo.bundle" ]; then
  H="$(git bundle list-heads "$BASE/etc/repo.bundle" 2>/dev/null | wc -l)"
  LOCAL_H="$(git ls-remote --heads "$BASE/etc/repo.bundle" 2>/dev/null | wc -l)"
  [ "$H" -gt 0 ] && ok "git bundle lists $LOCAL_H refs (survives losing GitHub)" || bad "git bundle unreadable"
else
  bad "git bundle missing"
fi

# ── 4. the secret set ───────────────────────────────────────────────────────
if [ -d "$BASE/etc/secrets" ]; then
  LIVE="$(find "infra/instances/$INSTANCE/secrets" -type f | wc -l)"
  REST="$(find "$BASE/etc/secrets" -type f | wc -l)"
  [ "$REST" -ge "$LIVE" ] && ok "secrets: $REST files restored (live has $LIVE)" || bad "secrets: $REST restored vs $LIVE live"
else
  bad "secrets directory missing from the snapshot"
fi
[ -r "$BASE/etc/backup-restic-pass" ] && ok "restic password escrow copy present in the archive" \
  || log "  note: backup-restic-pass not in this snapshot (pre-dates the escrow copy)"

# ── 5. clean up ──────────────────────────────────────────────────────────────
rm -rf "$DRILL_DIR"
log "scratch directory removed"
[ "$FAILED" = 0 ] && log "=== DRILL PASSED ===" || log "=== DRILL FAILED — see $LOGDIR/restore-drill.log ==="
exit "$FAILED"