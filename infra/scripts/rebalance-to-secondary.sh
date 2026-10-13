#!/usr/bin/env bash
# Rebalance: move large, path-stable, non-live directories from the NVMe (/) to the
# secondary SATA disk (/mnt/storage, 866 GB free), leaving a symlink so every existing
# path keeps working.
#
# Why symlinks and not bind mounts: a path that stays a path survives reboots, backups
# and anyone reading a config — a bind mount has to be re-established and is invisible in
# `ls`. Cheap, reversible, and the failure mode is obvious.
#
# What is deliberately NOT here:
#   - /var/lib/docker — 149 GB and the single biggest consumer, but it is LIVE container
#     I/O and this disk is rotational: containers would get measurably slower. It also
#     needs a full Docker restart, and the stack has an ordering hazard (gates do OIDC
#     discovery once at boot; Synapse CRASHES on a 502 rather than retrying). Deferred,
#     as a decision with a window — not smuggled in as cleanup.
#   - /opt/app/storage — 34 GB, but its data/ half is bind-mounted by running containers
#     and referenced by compose; geo-data is rebuildable and low value. Per-path decision.
#   - ~/.hermes — the agent's own live state. Never move it while the agent is running.
#
# Safety: rsync first, VERIFY the copy, only then remove the source, only then symlink.
# If verification fails the source is left untouched. An interrupted run is resumable.
#
# Usage: infra/scripts/rebalance-to-secondary.sh [--dry-run]
set -euo pipefail

DEST_ROOT="${DEST_ROOT:-/mnt/storage/home}"
DRY=""; [ "${1:-}" = "--dry-run" ] && DRY=1
MOVES=(
  "/home/service/comfy"
  "/home/service/models"
  "/home/service/Downloads"
)

log() { printf '%s  %s\n' "$(date -Is)" "$*"; }
die() { log "FATAL: $*"; exit 1; }

[ -d /mnt/storage ] || die "/mnt/storage is not mounted"
AVail="$(df -Pk /mnt/storage | tail -1 | awk '{print $4}')"
log "secondary disk free: $(( AVail / 1048576 )) GiB"

for src in "${MOVES[@]}"; do
  [ -d "$src" ] || { log "skip (absent): $src"; continue; }
  if [ -L "$src" ]; then log "skip (already a symlink): $src"; continue; fi

  size_kb="$(du -sk "$src" | awk '{print $1}')"
  log "--- $src ($(( size_kb / 1048576 )) GiB)"

  # In use? Refuse rather than yank a directory out from under a running process.
  # NOT `fuser -m`: that means "users of the FILE SYSTEM containing this path", so on a
  # directory under / it reports every process on the machine and skips everything always.
  # `lsof +D` is the correct question — is any file BENEATH this path open?
  if command -v lsof >/dev/null 2>&1; then
    n=$(timeout 40 lsof +D "$src" 2>/dev/null | tail -n +2 | wc -l)
    if [ "$n" -gt 0 ]; then
      log "    IN USE — $n open file(s) beneath it. Skipping; stop the process first."
      timeout 20 lsof +D "$src" 2>/dev/null | tail -n +2 | head -3 | awk '{printf "      %s pid %s\n", $1, $2}'
      continue
    fi
  fi

  dst="$DEST_ROOT$(dirname "$src")/$(basename "$src")"
  mkdir -p "$(dirname "$dst")"
  if [ -n "$DRY" ]; then log "    would copy → $dst, verify, remove source, symlink"; continue; fi

  log "    copying → $dst"
  rsync -a --info=stats2 "$src/" "$dst/" 2>&1 | tail -2 | sed 's/^/      /'

  # VERIFY before removing anything: same file count, same total size
  s_n=$(find "$src" -mindepth 1 | wc -l); d_n=$(find "$dst" -mindepth 1 | wc -l)
  s_b=$(du -sb "$src" | cut -f1);        d_b=$(du -sb "$dst" | cut -f1)
  if [ "$s_n" != "$d_n" ] || [ "$s_b" != "$d_b" ]; then
    log "    VERIFY FAILED (src $s_n files/$s_b B vs dst $d_n/$d_b) — SOURCE LEFT ALONE"
    continue
  fi
  log "    verified: $d_n entries, $(( d_b / 1048576 )) MiB"

  mv "$src" "${src}.moved-$(date +%s)" && log "    source parked as ${src}.moved-*"
  ln -s "$dst" "$src" && log "    symlinked: $src → $dst"
  rm -rf "${src}".moved-* 2>/dev/null && log "    old copy removed"
done

log "=== done ==="
df -h / /mnt/storage | tail -2 | sed 's/^/  /'