#!/usr/bin/env bash
# Golden artifacts — images that are NOT rebuildable, saved into the archive.
#
# docs/BACKUP.md tier 3 excludes container images because they are supposed to be
# rebuildable from the repo. That assumption is false for a specific, named set, and
# pretending otherwise is how data is lost: an exception that isn't written down is a
# hole, not a policy.
#
# Current members (see infra/build/images/manifest.yaml):
#   irlcoop/nocodb-gate-sso:2026.08.3    the runtime base the fork's Dockerfile.irlcoop
#                                        FROMs — a LOCAL-ONLY tag. Prune it and the
#                                        fork's build recipe stops working.
#   irlcoop/nocodb-gate-sso:2026.08.12   deployed, and the only home of the compiled
#                                        nc-gui frontend (49 MB / 854 files). The fork
#                                        commits zero _nuxt files and never builds the
#                                        frontend, so it cannot regenerate this.
#
# Saved once with `docker save | zstd` into /mnt/storage/golden-images/. backup.sh picks
# that directory up, so the artifacts land in the restic archive on surfy AND, through
# the mirror, on the offsite IPFS node. Re-running is cheap: an image whose file already
# exists is skipped, so only a NEW golden image costs transfer.
#
# Usage: infra/scripts/golden-images.sh [--force]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DEST="${DEST:-/mnt/storage/golden-images}"
LOGDIR="$ROOT/.logs"
FORCE=""; [ "${1:-}" = "--force" ] && FORCE=1

IMAGES="${IMAGES:-irlcoop/nocodb-gate-sso:2026.08.3 irlcoop/nocodb-gate-sso:2026.08.12}"

mkdir -p "$DEST" "$LOGDIR"
log() { printf '%s  %s\n' "$(date -Is)" "$*" | tee -a "$LOGDIR/golden-images.log"; }
log "=== golden artifacts → $DEST ==="

for img in $IMAGES; do
  if ! docker image inspect "$img" >/dev/null 2>&1; then
    log "MISSING locally, cannot save: $img  ← if this is gone, the artifact is gone"
    continue
  fi
  file="$DEST/$(echo "$img" | tr '/:' '__').tar.zst"
  if [ -f "$file" ] && [ -z "$FORCE" ]; then
    log "already saved: $(basename "$file") ($(du -h "$file" | cut -f1))"
    continue
  fi
  log "saving $img …"
  docker save "$img" | zstd -T0 -q -6 -o "$file"
  log "  → $(basename "$file") $(du -h "$file" | cut -f1)"
done

log "--- contents ---"
ls -lh "$DEST" | tail -n +2 | awk '{printf "  %s  %s\n", $5, $9}'
log "=== done (backup.sh will carry this into the archive) ==="