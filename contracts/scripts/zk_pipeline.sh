#!/usr/bin/env bash
# P2 zk pipeline — reproducible Groth16 build for the spend-treasury circuit.
# Toolchain lives under /mnt/storage/zk (the repurposed sda1, 870G free).
# Usage:  bash scripts/zk_pipeline.sh circuits/spend.circom  /mnt/storage/zk/build
# The mult2 sanity gate proved the whole chain on this host (compile -> ptau ->
# setup -> prove -> verify -> snarkjs OK).
set -euo pipefail

CIRCOM=/mnt/storage/zk/bin/circom
SNARKJS=/home/service/development/irl-coop-stack-v2/node_modules/.bin/snarkjs

CIRCUIT="${1:-circuits/spend.circom}"
OUT="${2:-/mnt/storage/zk/build}"
mkdir -p "$OUT"
NAME=$(basename "$CIRCUIT" .circom)
SRCDIR=$(dirname "$CIRCUIT")

PTAU0="$OUT/${NAME}_0000.ptau"
PTAU1="$OUT/${NAME}_0001.ptau"
PTAUF="$OUT/${NAME}_final.ptau"
ZK1="$OUT/${NAME}_0000.zkey"
ZK2="$OUT/${NAME}_0001.zkey"
VK="$OUT/${NAME}_vk.json"

echo "== compile ($CIRCOM) =="
"$CIRCOM" "$CIRCUIT" --r1cs --wasm --sym -o "$OUT"

echo "== powers of tau (230s) =="
"$SNARKJS" powersoftau new bn128 14 "$PTAU0"
echo "coop entropy $(date +%s)" | "$SNARKJS" powersoftau contribute "$PTAU0" "$PTAU1"
"$SNARKJS" powersoftau prepare phase2 "$PTAU1" "$PTAUF"

echo "== groth16 setup + define + export vk =="
"$SNARKJS" groth16 setup "$OUT/$NAME.r1cs" "$PTAUF" "$ZK1"
echo "coop entropy $(date +%s)" | "$SNARKJS" zkey contribute "$ZK1" "$ZK2"
"$SNARKJS" zkey export verificationkey "$ZK2" "$VK"

echo "== done =="
echo "  verifier key : $VK"
echo "  proving key  : $ZK2"
echo "  (a real witness needs circuit-specific input; wire per circuit.)"