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

# powers of tau size (log2 of the constraint ceiling). 14 fits spend (~8.4k);
# family circuits (ticket ~8.6k, badge/geo heads) need more headroom. Default 15
# covers the pilot family with margin at sane time/RAM; raise for the full set.
PTO="${ZK_PTO:-15}"

echo "== compile ($CIRCOM) =="
"$CIRCOM" "$CIRCUIT" --r1cs --wasm --sym -o "$OUT"

echo "== powers of tau (new bn128 $PTO) =="
"$SNARKJS" powersoftau new bn128 "$PTO" "$PTAU0"
echo "coop entropy $(date +%s)" | "$SNARKJS" powersoftau contribute "$PTAU0" "$PTAU1"
"$SNARKJS" powersoftau prepare phase2 "$PTAU1" "$PTAUF"

echo "== groth16 setup + define + export vk =="
"$SNARKJS" groth16 setup "$OUT/$NAME.r1cs" "$PTAUF" "$ZK1"
echo "coop entropy $(date +%s)" | "$SNARKJS" zkey contribute "$ZK1" "$ZK2"
"$SNARKJS" zkey export verificationkey "$ZK2" "$VK"

# The on-chain verifier is what the pool's IShieldedPoolVerifier seam consumes.
VERIFIER_SOL="$OUT/${NAME}_Verifier.sol"
echo "== export on-chain verifier =="
"$SNARKJS" zkey export solidityverifier "$ZK2" "$VERIFIER_SOL"

# Canonical name: the final contributed zkey. The internal setup produces
# *_0001.zkey (ZK2) after the phase-2 contribute; the stack (stack-prove.sh /
# stack-report.py) checks for *_final.zkey by design. Emit the canonical link so
# the check matches the real artifact.
cp "$ZK2" "$OUT/${NAME}_final.zkey"

echo "== done =="
echo "  verifier key  : $VK"
echo "  verifier.sol  : $VERIFIER_SOL"
echo "  proving key   : $OUT/${NAME}_final.zkey"
echo "  (wire the verifier.sol into the pool's setVerifier for the P2 gate.)"