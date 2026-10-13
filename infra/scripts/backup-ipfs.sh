#!/usr/bin/env bash
# Mirror the stack's restic repository to the off-host IPFS node, and pin it.
#
# This is the OFFSITE tier. surfy's USB (/mnt/usb) is a second copy on the same LAN —
# it survives a dead disk, a bad upgrade, a stolen machine, but not fire, flood, or a
# break-in. 137.184.24.48 is a DigitalOcean box: a genuinely different failure domain,
# behind a public gateway anyone can read from.
#
# How it works, and why each step is cheap:
#   1. `restic copy`       replicate our repo (on surfy) to a LOCAL mirror — incremental,
#                          integrity-checked, and it leaves a third copy on /mnt/storage.
#   2. `rsync`             mirror to the box. restic pack files are immutable, so only
#                          new packs move. First run is ~270 MB; later ones are MBs.
#   3. `ipfs add -r --pin` add and pin there. IPFS dedups identical blocks, so only new
#                          blocks are stored. The CLI drives the running daemon via
#                          --api; the backup account needs no repo of its own and no sudo.
#   4. pin new, THEN unpin the previous root — so the node holds roughly one copy of the
#                          current repository, not a growing pile of historical roots.
#
# Safety rails, deliberately:
#   - does not run `ipfs repo gc` on that node. gc only removes UNPINNED blocks (pinned
#     content is safe), but it is the node owner's deliberate maintenance step, not ours
#     to trigger — it could also drop someone's unpinned work. Note the consequence: each
#     restic prune leaves our superseded packs stored-but-unreachable, so that node needs a
#     periodic `ipfs repo gc` or it slowly fills with our dead weight.
#   - pins the new root BEFORE unpinning the old, so there is never a window with neither.
#   - warns when the node's repo passes 80% of its StorageMax (it sits at ~65% already).
#
# Usage: infra/scripts/backup-ipfs.sh [--dry-run]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
INSTANCE="${INSTANCE:-dev}"

IPFS_HOST="${IPFS_HOST:-137.184.24.48}"
IPFS_USER="${IPFS_USER:-irlbackup}"
IPFS_KEY="${IPFS_KEY:-$HOME/.ssh/id_ed25519_ipfs}"
IPFS_DIR="${IPFS_DIR:-/home/irlbackup/restic}"
IPFS_API="${IPFS_API:-/ip4/127.0.0.1/tcp/5001}"

# source repo (surfy) and the local mirror staged for the transfer
SRC_REPO="${SRC_REPO:-sftp:service@surfy:/mnt/usb/irl-backup/restic}"
MIRROR_LOCAL="${MIRROR_LOCAL:-/mnt/storage/restic-mirror}"
RESTIC_PASSWORD_FILE="${RESTIC_PASSWORD_FILE:-$ROOT/infra/instances/$INSTANCE/secrets/backup-restic-pass}"
MANIFEST="${MANIFEST:-$ROOT/infra/backup-cids.json}"

SSH=(ssh -i "$IPFS_KEY" -o BatchMode=yes -o ConnectTimeout=15 "$IPFS_USER@$IPFS_HOST")
RSH="ssh -i $IPFS_KEY -o BatchMode=yes -o ConnectTimeout=15"
LOGDIR="$ROOT/.logs"

export RESTIC_PASSWORD_FILE
mkdir -p "$LOGDIR"
log() { printf '%s  %s\n' "$(date -Is)" "$*" | tee -a "$LOGDIR/backup-ipfs.log"; }
die() { log "FATAL: $*"; exit 1; }

DRY=""; [ "${1:-}" = "--dry-run" ] && DRY="--dry-run"

# One run at a time. The node is a 1 GB / ~1 vCPU droplet: two concurrent `ipfs add -r`
# runs saturate it, and the loser came back with EMPTY output and failed — which looked
# like a mystery until the duplication was found. A lock is the fix, not more retries.
mkdir -p "$LOGDIR"
exec 9>"$LOGDIR/.backup-ipfs.lock"
flock -n 9 || { echo "another backup-ipfs run already holds the lock — not starting a second one"; exit 0; }

log "=== ipfs mirror start → $IPFS_USER@$IPFS_HOST:$IPFS_DIR ==="

# ── 0. the node ──────────────────────────────────────────────────────────────
NODE="$("${SSH[@]}" "curl -s --max-time 10 -X POST http://127.0.0.1:5001/api/v0/repo/stat" 2>/dev/null || true)"
[ -n "$NODE" ] || die "the kubo API did not answer on $IPFS_HOST — is the daemon up?"
USED="$(printf '%s' "$NODE" | tr ',' '\n' | awk -F: '/RepoSize/{print $2}')"
MAX="$(printf '%s' "$NODE" | tr ',' '\n' | awk -F: '/StorageMax/{print $2}')"
PCT=$(( USED * 100 / MAX ))
log "node repo: $(( USED / 1048576 )) MiB of $(( MAX / 1048576 )) MiB (${PCT}%)"
[ "$PCT" -ge 80 ] && log "WARNING: node repo at ${PCT}% of StorageMax — raise it or reduce retention"

# ── 1. replicate our repo to the local mirror ────────────────────────────────
mkdir -p "$MIRROR_LOCAL"
if [ ! -f "$MIRROR_LOCAL/config" ]; then
  log "initializing local mirror at $MIRROR_LOCAL"
  [ -z "$DRY" ] && restic -r "$MIRROR_LOCAL" init 2>&1 | tail -1 | tee -a "$LOGDIR/backup-ipfs.log"
fi
log "restic copy: $SRC_REPO → $MIRROR_LOCAL"
# restic ≥0.17 form: -r is the DESTINATION, --from-repo the source, and the source
# password comes from --from-password-file (the global RESTIC_PASSWORD_FILE covers the dest).
restic -r "$MIRROR_LOCAL" copy --from-repo "$SRC_REPO" \
       --from-password-file "$RESTIC_PASSWORD_FILE" $DRY 2>&1 \
  | tee -a "$LOGDIR/backup-ipfs.log" | tail -3
log "mirror size: $(du -sh "$MIRROR_LOCAL" | cut -f1)"

# ── 2. mirror to the box ─────────────────────────────────────────────────────
log "rsync → $IPFS_USER@$IPFS_HOST:$IPFS_DIR"
rsync -a --delete-after --partial --no-perms --no-owner --no-group \
      --exclude 'locks/' \
      -e "$RSH" "$MIRROR_LOCAL/" "$IPFS_USER@$IPFS_HOST:$IPFS_DIR/" \
      $([ -n "$DRY" ] && echo --dry-run) 2>&1 | tail -3 | tee -a "$LOGDIR/backup-ipfs.log"

# ── 3. add + pin on the node ─────────────────────────────────────────────────
# Add the tree, then identify the repository root BY ITS LINKS.
#
# Do not trust the order of `ipfs add` output. -q prints one line per file; -Q is meant
# to print only the final root but is NOT reliable for directories on kubo 0.12 with
# concurrent workers — a pack file can come last, and a file CID resolves perfectly well
# as an object while being completely wrong. So: test the candidates and take the one
# that actually looks like a restic repository.
# Identify the repository root BY NAME, from the unflagged `ipfs add` output.
#
# Do NOT use `-q`: it prints one bare CID per file with no name, so the root is
# indistinguishable from any pack file, and any attempt to guess from ordering is
# unreliable for directories on kubo 0.12 with concurrent workers. Without `-q`, each
# line reads `added <cid> <path>`, and the directory's own line names the directory —
# so the root is the line whose final field IS the directory's basename.
log "ipfs add -r (root identified by name, never by output order)"
BASE_NAME="$(basename "$IPFS_DIR")"
# Let the node FLUSH the rsync first. It has 1 GB of RAM and no swap: adding immediately
# after a 1 GB push means hashing while the daemon is still absorbing write-back, and on
# that box the add comes back truncated (33 lines instead of 332) and looks like a mystery.
# Alone the same add takes ~14 s. Sequencing is the fix.
log "settling the node after the push (sync)"
"${SSH[@]}" "sync" >/dev/null 2>&1 || true
sleep 5

# Stderr (the progress chatter) is kept for diagnosis; stdout is the `added ...` lines.
# Two attempts, because a truncated walk is the observed failure mode on this box.
ADD_OUT=""
for attempt in 1 2; do
  ADD_OUT="$("${SSH[@]}" "timeout 900 ipfs --api $IPFS_API add -r --pin=false '$IPFS_DIR'" 2>>"$LOGDIR/ipfs-add.stderr" || true)"
  n=$(printf '%s\n' "$ADD_OUT" | grep -c '^added ' || true)
  log "  add attempt $attempt: $n lines"
  # a complete walk ends with a line for every file PLUS the directory itself
  printf '%s\n' "$ADD_OUT" | awk -v b="$(basename "$IPFS_DIR")" '$1=="added" && $NF==b {found=1} END{exit !found}' && break
  [ "$attempt" = 1 ] && log "  truncated walk — waiting and retrying"
  sleep 15
done
[ -n "$ADD_OUT" ] || die "ipfs add produced NO output — daemon busy or another run in progress; see $LOGDIR/ipfs-add.stderr"

NEW_CID="$(printf '%s\n' "$ADD_OUT" | awk -v b="$BASE_NAME" '$1=="added" && $NF==b {print $2}' | tail -1)"
[ -n "$NEW_CID" ] || die "no add-output line names '$BASE_NAME' as the final field — refusing to pin (lines: $(printf '%s\n' "$ADD_OUT" | wc -l))"

# Verify it really is the repository root before pinning: a name match alone could pick a
# FILE that happens to be called `restic`.
L="$("${SSH[@]}" "ipfs --api $IPFS_API ls '$NEW_CID'" 2>/dev/null || true)"
for want in config data index keys snapshots; do
  printf '%s' "$L" | grep -q " $want" \
    || die "root candidate $NEW_CID lacks '$want' — refusing to pin it"
done
log "root CID identified by its links: $NEW_CID"

"${SSH[@]}" "ipfs --api $IPFS_API pin add '$NEW_CID'" >/dev/null 2>&1 || die "pin add failed for $NEW_CID"
log "pinned"

# Prove the PUBLIC read path in the same run. Warn rather than fail: Cloudflare can lag
# behind a fresh pin, and a lagging gateway does not make the pin wrong.
GW="${IPFS_GATEWAY:-https://ipfs.nftbookbazaar.com}"
CODE="$(curl -s -o /dev/null -w '%{http_code}' --max-time 30 "$GW/ipfs/$NEW_CID/config" 2>/dev/null || echo 000)"
log "gateway check: $GW/ipfs/$NEW_CID/config → HTTP $CODE"
[ "$CODE" = "200" ] || log "WARNING: gateway did not serve the new root (CF can lag; the pin itself is set)"

# ── 4. unpin the previous root, now that the new one is pinned ───────────────
PREV=""
[ -f "$MANIFEST" ] && PREV="$(python3 -c "
import json,sys
try:
    d=json.load(open('$MANIFEST'))
    print(d['runs'][-1]['cid'] if d.get('runs') else '')
except Exception: print('')
" 2>/dev/null || echo '')"
if [ -n "$PREV" ] && [ "$PREV" != "$NEW_CID" ]; then
  log "unpinning previous root $PREV (the newest is pinned; older CID stays in the manifest as the audit trail)"
  "${SSH[@]}" "ipfs --api $IPFS_API pin rm '$PREV'" 2>&1 | tail -1 | tee -a "$LOGDIR/backup-ipfs.log"
fi

# ── 5. record it, in the repo, so the CID list is itself backed up ───────────
if [ -z "$DRY" ]; then
  RESTIC_SNAP="$(restic -r "$MIRROR_LOCAL" snapshots --json 2>/dev/null | python3 -c "
import json,sys
s=json.load(sys.stdin); print(s[-1]['short_id'] if s else '')" || echo '')"
  python3 - "$MANIFEST" "$NEW_CID" "$RESTIC_SNAP" "$(du -sb "$MIRROR_LOCAL" | cut -f1)" "$IPFS_HOST" <<'PY'
import json, sys, datetime, os
manifest, cid, snap, size, host = sys.argv[1:6]
d = {"note": "Mirrors of the restic repository on the off-host IPFS node. The newest run is "
             "pinned; older CIDs are the audit trail. Fetch: https://ipfs.nftbookbazaar.com/ipfs/<cid>",
     "gateway": "https://ipfs.nftbookbazaar.com", "runs": []}
if os.path.exists(manifest):
    try: d = json.load(open(manifest))
    except Exception: pass
d.setdefault("runs", []).append({
    "at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
    "cid": cid, "restic_snapshot": snap, "repo_bytes": int(size), "node": host})
json.dump(d, open(manifest, "w"), indent=2)
open(manifest, "a").write("\n")
print(f"manifest: {len(d['runs'])} run(s) recorded")
PY
  log "manifest: $MANIFEST"
fi

log "=== ipfs mirror complete ==="
log "verify from anywhere:  https://ipfs.nftbookbazaar.com/ipfs/$NEW_CID"
log "restore path:          fetch the repo by CID → restic -r <dir> snapshots → infra/scripts/restore-drill.sh"