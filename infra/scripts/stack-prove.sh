#!/usr/bin/env bash
# stack-prove.sh — P2 proving-layer bring-up (declared app: zk-proving).
#
# Idempotent and honest. It does NOT build a zkey on boot: a Groth16 key is a
# trusted-setup article; rebuilding it every boot is ceremony churn and would
# invalidate every existing proof. So this script:
#
#   1. CHECKS the artifact home for the spend verification key + proving key,
#   2. if present: reports OK (the *wiring* of setVerifier is the P2 gate, which
#      is deliberate, not automatic on boot), and
#   3. if missing: FLAGS "zk: key missing — run the one-time ceremony" so the
#      gap is visible in the status report instead of being a silent /tmp path.
#
# Either way it exits 0 — a missing key is a flag, not a fatal bring-up (the
# P1 no-op verifier keeps flowing until the real one is wired). Run by
# stack-up.sh for the `zk-proving` app in place of the no-compose SKIP line.
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
KEY_DIR="${ZK_KEY_DIR:-/mnt/storage/zk/keys}"
NAME="spend"          # single-key-per-pool decision: one spend key today

say()  { printf '\033[1;34m== %s\033[0m\n' "$*"; }
ok()   { printf '  \033[32mOK\033[0m   %s\n' "$*"; }
flag() { printf '  \033[33mFLAG\033[0m %s\n' "$*"; }

say "zk-proving (P2 proving layer)"

VK="$KEY_DIR/${NAME}_vk.json"
PROVING_KEY="$KEY_DIR/${NAME}_final.zkey"

if [ -f "$VK" ] && [ -f "$PROVING_KEY" ]; then
  ok "$NAME setup present: $VK + $PROVING_KEY"
  ok "a real verifier can be wired (the P2 gate)."
  flag "NoopVerifier still in the pool until the deliberate setVerifier step."
  exit 0
fi

flag "zk: key missing — run the one-time ceremony"
flag "  bash $ROOT/contracts/zk/build.sh      # builds $NAME setup into $KEY_DIR"
flag "  then wire setVerifier(real) on the local chain (the P2 gate)"
exit 0