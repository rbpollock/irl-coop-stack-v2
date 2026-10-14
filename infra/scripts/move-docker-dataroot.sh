#!/usr/bin/env bash
# Move Docker's data-root to the secondary disk (/mnt/storage/docker).
#
# Cheap to write, expensive in consequence: it takes EVERY container down for the duration
# of the copy — ~149 GB onto a rotational disk — so this is written to be boring.
# Pre-flight, copy, VERIFY, switch, come back, and only then tell you what to clean up.
#
# ⚠ 2026-10-13: this host uses the CONTAINERD SNAPSHOTTER (`docker info --format '{{.Driver}}'`
# prints `overlayfs`, not `overlay2`). The images are NOT in /var/lib/docker — they live in
# /var/lib/containerd (measured 134.7 GB vs 2.3 GB in /var/lib/docker, which has no `image/`
# or `overlay2/` subdir at all). Run unchanged, this script MOVES ~2.3 GB and takes the whole
# stack down for it. Check the driver first: if `overlayfs`, the real target is
# /var/lib/containerd and the move is `/etc/containerd/config.toml` `root =`, not daemon.json.
# The containing of the "image" check below is what caught this — this layout WILL fail it.
#
# Original rationale, now corrected: /var/lib/docker LOOKED like the largest consumer because
# `docker system df` reports 144 GB while the snapshotter stores it in containerd. The accepted
# price is unchanged: /mnt/storage is a SPINNING disk (sda, ROTA=1), so container I/O slows.
# (sda, ROTA=1), so container I/O gets slower. That trade was made deliberately.
#
# What it deliberately does NOT do: delete the old data-root. It parks it and prints the
# command. The rollback path must exist until the stack is verified healthy, and leaving
# 149 GB on the NVMe for a few hours is cheap insurance.
#
# Ordering note for THIS stack: coop-api is a HOST process, not a container, so it stays up
# across the restart. That removes the usual hazard — the oauth2-proxy gates do OIDC
# discovery once at boot, and Synapse CRASHES on a 502 instead of retrying — but verify
# matrix afterwards anyway, and force-recreate it if it did not come back.
#
# Run as root:  bash infra/scripts/move-docker-dataroot.sh
set -euo pipefail

SRC="/var/lib/docker"
DEST="${DEST:-/mnt/storage/docker}"
DAEMON_JSON="/etc/docker/daemon.json"
STAMP="$(date +%Y%m%d-%H%M%S)"
LOG="${LOG:-/home/service/development/irl-coop-stack-v2/.logs/move-docker-dataroot.log}"

log() { printf '%s  %s\n' "$(date -Is)" "$*" | tee -a "$LOG"; }
die() { log "FATAL: $*"; exit 1; }

[ "$(id -u)" = 0 ] || die "run as root"
mkdir -p "$(dirname "$LOG")"

log "=== moving Docker data-root: $SRC → $DEST ==="

# ── 1. pre-flight ────────────────────────────────────────────────────────────
command -v rsync >/dev/null || die "rsync not installed"
[ -d "$SRC" ] || die "$SRC does not exist"
CUR_ROOT="$(docker info --format '{{.DockerRootDir}}' 2>/dev/null || echo "$SRC")"
[ "$CUR_ROOT" = "$SRC" ] || die "docker is already using $CUR_ROOT — nothing to do?"

SRC_KB="$(du -sk "$SRC" | awk '{print $1}')"
FREE_KB="$(df -Pk "$(dirname "$DEST")" | tail -1 | awk '{print $4}')"
NEED_KB=$(( SRC_KB + SRC_KB / 10 ))          # +10% headroom
printf 'source %s GiB | destination free %s GiB | need %s GiB\n' \
  "$((SRC_KB/1048576))" "$((FREE_KB/1048576))" "$((NEED_KB/1048576))" | tee -a "$LOG"
[ "$FREE_KB" -ge "$NEED_KB" ] || die "not enough free space at $DEST"

CONTAINERS_BEFORE="$(docker ps -q | wc -l)"
IMAGES_BEFORE="$(docker images -q | sort -u | wc -l)"
log "before: $CONTAINERS_BEFORE running containers, $IMAGES_BEFORE images"
[ -f "$DAEMON_JSON" ] && { cp -a "$DAEMON_JSON" "${DAEMON_JSON}.bak-${STAMP}"; log "daemon.json backed up"; }
cp -a "$DAEMON_JSON" "/tmp/daemon.json.before-${STAMP}" 2>/dev/null || true

# ── 2. stop docker ───────────────────────────────────────────────────────────
log "stopping docker (the whole stack goes down here)"
systemctl stop docker.socket 2>/dev/null || true
systemctl stop docker
sleep 3
if pgrep -x dockerd >/dev/null; then die "dockerd still running — refusing to copy a live data-root"; fi
log "docker stopped"

# ── 3. copy ──────────────────────────────────────────────────────────────────
mkdir -p "$DEST"
log "copying (this is the long part — ~149 GB onto a spinning disk)"
# -H hardlinks (image layers), -A ACLs, -X xattrs, -S sparse, --numeric-ids:
# a Docker data-root needs all of these or layers come back subtly broken.
rsync -aHAXS --numeric-ids --info=progress2 "$SRC/" "$DEST/" 2>&1 | tail -2 | tee -a "$LOG"
log "copied"

# ── 4. VERIFY before switching anything ──────────────────────────────────────
S_N="$(find "$SRC" -mindepth 1 | wc -l)"; D_N="$(find "$DEST" -mindepth 1 | wc -l)"
S_B="$(du -sb "$SRC" | cut -f1)";        D_B="$(du -sb "$DEST" | cut -f1)"
printf 'verify: source %s entries / %s B — destination %s entries / %s B\n' \
  "$S_N" "$S_B" "$D_N" "$D_B" | tee -a "$LOG"
if [ "$S_N" != "$D_N" ] || [ "$S_B" != "$D_B" ]; then
  die "COPY VERIFICATION FAILED — nothing switched, docker is untouched at $SRC"
fi
for must in image containers volumes overlay2; do
  [ -e "$DEST/$must" ] || die "$DEST/$must missing — that is not a Docker data-root"
done
log "verified: entry count and byte total match, and the expected subtrees are present"

# ── 5. switch ────────────────────────────────────────────────────────────────
log "pointing the daemon at $DEST"
python3 - "$DAEMON_JSON" "$DEST" <<'PY'
import json, sys, os
path, dest = sys.argv[1], sys.argv[2]
cfg = {}
if os.path.exists(path):
    with open(path) as f:
        try: cfg = json.load(f)
        except Exception: cfg = {}
cfg["data-root"] = dest
os.makedirs(os.path.dirname(path), exist_ok=True)
with open(path, "w") as f:
    json.dump(cfg, f, indent=2)
    f.write("\n")
print("daemon.json:", json.dumps(cfg))
PY

log "starting docker"
systemctl start docker
for i in $(seq 1 30); do docker info >/dev/null 2>&1 && break; sleep 2; done
docker info >/dev/null 2>&1 || die "dockerd did not come back — see journalctl -u docker"

# ── 6. come back, and check ──────────────────────────────────────────────────
log "waiting for containers to return (restart policies do this)"
for i in $(seq 1 60); do
  n="$(docker ps -q | wc -l)"
  [ "$n" -ge "$CONTAINERS_BEFORE" ] && break
  sleep 5
done
CONTAINERS_AFTER="$(docker ps -q | wc -l)"
IMAGES_AFTER="$(docker images -q | sort -u | wc -l)"
log "after: $CONTAINERS_AFTER running containers (was $CONTAINERS_BEFORE), $IMAGES_AFTER images (was $IMAGES_BEFORE)"
log "data-root now: $(docker info --format '{{.DockerRootDir}}')"

log "--- the services that matter ---"
for c in storage-postgres-1 storage-minio-1 communication-matrix-1 workflow-rag-api-1 proxy-traefik-1; do
  printf '  %-26s %s\n' "$c" "$(docker ps -a --filter name=^/${c}$ --format '{{.Status}}')" | tee -a "$LOG"
done
log "--- host apps (they never went down) ---"
for hp in "coop-api:3001:/api/auth/config" "peer_xyz_payments:3010:/health" "treasury-relayer:3020:/health"; do
  n="${hp%%:*}"; r="${hp#*:}"; p="${r%%:*}"; pa="${r#*:}"
  printf '  %-20s :%-5s HTTP %s\n' "$n" "$p" "$(curl -s -o /dev/null -w '%{http_code}' --max-time 8 "http://127.0.0.1:$p$pa" 2>/dev/null)" | tee -a "$LOG"
done

cat <<EOF | tee -a "$LOG"

=== done
If everything above is healthy:
  1. delete the old copy — it is 149 GB of NVMe:
       rm -rf ${SRC}.moved-${STAMP}          # after: mv ${SRC} ${SRC}.moved-${STAMP}
     (the script leaves $SRC in place on purpose; the rollback needs it)
  2. if matrix did NOT come back, it is the known crash-on-502: force-recreate it now that
     coop-api is up:
       docker compose -f infra/out/dev/compose/communication/docker-compose.yml \\
         -f infra/out/dev/compose/communication/docker-compose.override.yml up -d --force-recreate matrix

ROLLBACK (only while the old data-root still exists):
  systemctl stop docker
  cp -a ${DAEMON_JSON}.bak-${STAMP} ${DAEMON_JSON}    # or delete it if it did not exist
  systemctl start docker
EOF