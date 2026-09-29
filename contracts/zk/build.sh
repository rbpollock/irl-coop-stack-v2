#!/usr/bin/env bash
# contracts/zk/build.sh — the P2 build recipe (wraps contracts/scripts/zk_pipeline.sh).
#
# Builds the Groth16 proving key + verifier key for a circuit into the persistent
# artifact home (/mnt/storage/zk/keys by default) — NEVER into infra/out/.
#
# This is the ONE-TIME CEREMONY path. It is NOT what stack-up runs every boot:
# stack-prove.sh only CHECKS for an existing key and wires the verifier; it does
# not rebuild one. Run this explicitly when you intend to (re)create a setup.
#
# Usage:
#   bash contracts/zk/build.sh [circuit] [key-dir]
#   default circuit: spend (the single-key-per-pool decision)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
KEY_DIR="${2:-/mnt/storage/zk/keys}"
CIRCUIT="${1:-$ROOT/contracts/circuits/spend.circom}"

[ -x /mnt/storage/zk/bin/circom ] || { echo "circom not installed — see p2-build-plan.md"; exit 1; }

mkdir -p "$KEY_DIR"

echo "== zk build: $(basename "$CIRCUIT") -> $KEY_DIR =="
bash "$ROOT/contracts/scripts/zk_pipeline.sh" "$CIRCUIT" "$KEY_DIR"

echo
echo "== complete. artifacts in $KEY_DIR =="
ls -la "$KEY_DIR" | grep -E 'zkey|vk.json|verifier|_fz' || true

echo
echo "== next: wire the verifier into the pool (stack-prove.sh / P2 gate) =="