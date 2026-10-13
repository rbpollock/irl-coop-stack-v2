#!/usr/bin/env bash
# Upgrade kubo on the IPFS node (137.184.24.48) — 0.12.0 (Mar 2022) → current.
#
# WHY THIS SCRIPT EXISTS AND IS CAREFUL: a kubo repo migration is FORWARD-ONLY. There is
# no downgrade short of restoring a backup, and this node serves ~2,552 recursive pins of
# other people's content. Every step below exists because the alternative is "the gateway
# went dark and we cannot go back".
#
# Order of operations, deliberately:
#   1. record the pre-state (version, repo version, pin list, config) — cheap, and it is
#      what makes an audit of the upgrade possible afterwards;
#   2. make a FULL COPY of the repo before touching anything. 6.9 GB into 11 GB free fits.
#      A same-disk copy protects against a failed migration, not against disk failure;
#   3. download the new binary and verify its published sha512 — never an unverified binary;
#   4. stop the daemon, keep the old binary, install the new one;
#   5. start, let it MIGRATE (this is the slow, risky part), then verify: repo version,
#      pin count unchanged, our own backup CID still resolvable, gateway answering.
#
# Run as root ON THE BOX:   bash upgrade-ipfs-node.sh [target-version]
set -euo pipefail

TARGET="${1:-v0.43.1}"                 # variable on purpose: pin the version you intend
ARCH="amd64"
REPO_DIR="${REPO_DIR:-/root/.ipfs}"
BIN="/usr/local/bin/ipfs"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="${REPO_DIR}.pre-${TARGET}-${STAMP}"
WORK="/var/tmp/kubo-upgrade-${STAMP}"
API='--api /ip4/127.0.0.1/tcp/5001'
OURS="${OURS:-QmW59SZGnMbYemKLdYHzECZzhEoR5AYT9FDCCkMhdnTELa}"   # our backup repo root

[ "$(id -u)" = 0 ] || { echo "run as root" >&2; exit 1; }
log() { printf '\n=== %s\n' "$*"; }

log "1. pre-state"
OLD_VER="$(ipfs version | awk '{print $3}')"
OLD_REPO="$(ipfs repo version)"
PINS_BEFORE="$(ipfs $API pin ls --type=recursive | wc -l)"
mkdir -p "$WORK"
ipfs $API pin ls --type=recursive > "$WORK/pins-before.txt"
ipfs config show > "$WORK/config-before.json" 2>/dev/null || cp "$REPO_DIR/config" "$WORK/config-before.json"
printf 'kubo %s | %s | %s pins\n' "$OLD_VER" "$OLD_REPO" "$PINS_BEFORE"
printf 'artifacts in %s (pin list + config — keep these)\n' "$WORK"
df -h "$REPO_DIR" | tail -1

log "2. full copy of the repository (the only real insurance)"
REPO_SIZE_KB="$(du -sk "$REPO_DIR" | awk '{print $1}')"
FREE_KB="$(df -Pk "$REPO_DIR" | tail -1 | awk '{print $4}')"
NEED_KB=$(( REPO_SIZE_KB + 500000 ))
printf 'repo %s MiB, free %s MiB, need %s MiB\n' \
  "$((REPO_SIZE_KB/1024))" "$((FREE_KB/1024))" "$((NEED_KB/1024))"
[ "$FREE_KB" -ge "$NEED_KB" ] || { echo "REFUSING: not enough free space for a safety copy" >&2; exit 1; }
cp -a "$REPO_DIR" "$BACKUP_DIR"
printf 'copied → %s (%s)\n' "$BACKUP_DIR" "$(du -sh "$BACKUP_DIR" | cut -f1)"

log "3. fetch kubo $TARGET and verify its published sha512"
cd "$WORK"
# Source: the GitHub release, NOT the canonical dist.ipfs.tech mirror. Verified 2026-10-13:
# dist.ipfs.tech is IPv6-only and the node has no IPv6 route, so it answers HTTP 000 there
# (and times out from this host too). The GitHub release carries the same tarball AND the
# same published .sha512, and is reachable from both.
BASE="https://github.com/ipfs/kubo/releases/download/${TARGET}/kubo_${TARGET}_linux-${ARCH}"
curl -fsSL -O "${BASE}.tar.gz" || { echo "download failed (is $TARGET a real kubo release?)" >&2; exit 1; }
curl -fsSL -o checksum.sha512 "${BASE}.tar.gz.sha512" || { echo "could not fetch the published checksum" >&2; exit 1; }
# the published file names the tarball; normalise it and verify
EXPECT="$(awk '{print $1}' checksum.sha512)"
ACTUAL="$(sha512sum "kubo_${TARGET}_linux-${ARCH}.tar.gz" | awk '{print $1}')"
if [ "$EXPECT" != "$ACTUAL" ]; then
  echo "REFUSING: sha512 mismatch — expected $EXPECT got $ACTUAL" >&2; exit 1
fi
echo "sha512 verified"
tar -xzf "kubo_${TARGET}_linux-${ARCH}.tar.gz"
NEWBIN="$WORK/kubo/ipfs"
[ -x "$NEWBIN" ] || { echo "tarball did not contain kubo/ipfs" >&2; exit 1; }
"$NEWBIN" version

log "4. stop the daemon and install the new binary"
systemctl stop ipfs
cp -a "$BIN" "${BIN}.bak-${OLD_VER}"      # rollback copy, named for its version
install -m 0755 "$NEWBIN" "$BIN"
"$BIN" version

log "5. start — the repo MIGRATION happens here and can take several minutes"
systemctl start ipfs
for i in $(seq 1 120); do
  if ipfs $API version >/dev/null 2>&1; then echo "API up after ${i}0s-ish"; break; fi
  sleep 10
done
journalctl -u ipfs -n 30 --no-pager | tail -15

log "6. verify — did the data survive the migration?"
NEW_VER="$(ipfs version | awk '{print $3}')"
NEW_REPO="$(ipfs repo version)"
PINS_AFTER="$(ipfs $API pin ls --type=recursive | wc -l)"
printf 'kubo %s → %s | %s → %s | pins %s → %s\n' "$OLD_VER" "$NEW_VER" "$OLD_REPO" "$NEW_REPO" "$PINS_BEFORE" "$PINS_AFTER"
ipfs $API repo stat | tr ',' '\n' | grep -E 'RepoSize|StorageMax' || true
echo "--- our backup repo still resolvable? ---"
if ipfs $API ls "$OURS" >/dev/null 2>&1; then echo "OK: $OURS resolves locally"; else echo "WARNING: $OURS does NOT resolve — check before touching the backup pipeline"; fi
echo "--- gateway ---"
curl -s -o /dev/null -w "gateway /ipfs/\$OURS/config → HTTP %{http_code}\n" --max-time 30 "https://ipfs.nftbookbazaar.com/ipfs/$OURS/config"

cat <<EOF

=== done: kubo $OLD_VER → $NEW_VER
IMPORTANT — two follow-ups, do not skip:
  1. The backup pipeline was written against 0.12. Re-run it and confirm the flags still
     behave:  bash infra/scripts/backup-ipfs.sh
     (add/pin/ls semantics have changed across 31 releases; the root-identification check
     in that script will catch it if the shape of `ipfs add` output changed.)
  2. Newer kubo ships a stricter gateway and different defaults. Check the public gateway
     still serves what it should, and re-read ${WORK}/config-before.json against the new
     'ipfs config show' for values that were renamed or dropped.

ROLLBACK if something is wrong (do this immediately, before the old blocks are touched):
  systemctl stop ipfs
  rm -rf $REPO_DIR
  mv $BACKUP_DIR $REPO_DIR
  cp -a ${BIN}.bak-${OLD_VER} $BIN
  systemctl start ipfs
  # then re-verify: ipfs repo version, pin count $PINS_BEFORE, and \$OURS resolving
Keep $BACKUP_DIR until you are satisfied — it is the only way back.
EOF