#!/usr/bin/env bash
# Deploy + verify the USDC router on a REAL network. The deploy key is read from a file so it
# never enters a shell history, a transcript, an env dump, or the repo.
#
#   bash scripts/deploy_router_testnet.sh base-sepolia 0x<GROUP_SAFE_ON_THAT_CHAIN>
#
# The key file (default ~/.secrets/base-sepolia.key) must contain ONLY the 0x-prefixed key.
# This script never prints it, and refuses to proceed if the file is readable by others.
set -euo pipefail

NET="${1:-base-sepolia}"
DEST="${2:-}"
KEYFILE="${DEPLOY_KEY_FILE:-$HOME/.secrets/base-sepolia.key}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

[ -n "$DEST" ] || { echo "usage: $0 <network> <destination-address-on-that-chain>"; exit 1; }
[ -f "$KEYFILE" ] || { echo "no key file at $KEYFILE — create it with the key from a funded account, chmod 600"; exit 1; }

# --- the key file itself must be private, or we are about to leak a key ---
PERMS=$(stat -c '%a' "$KEYFILE")
case "$PERMS" in
  600|400) : ;;
  *) echo "REFUSING: $KEYFILE is mode $PERMS (want 600). Run: chmod 600 $KEYFILE"; exit 1 ;;
esac

RPC=$(python3 -c "import json,sys;print(json.load(open('$ROOT/networks.json'))['$NET']['rpcUrl'])")
CHAIN=$(python3 -c "import json,sys;print(json.load(open('$ROOT/networks.json'))['$NET']['chainId'])")
USDC=$(python3 -c "import json,sys;print(json.load(open('$ROOT/networks.json'))['$NET'].get('usdc') or '')")
[ -n "$USDC" ] || { echo "REFUSING: no verified USDC recorded for $NET in networks.json"; exit 1; }

export PRIVATE_KEY="$(tr -d '[:space:]' < "$KEYFILE")"
case "$PRIVATE_KEY" in 0x*) : ;; *) echo "REFUSING: the key file does not start with 0x"; exit 1 ;; esac

# --- who is paying, and can they? (asked through hardhat, so the key stays in the env only) ---
cd "$ROOT"
npx hardhat run scripts/whoami.ts --network "$NET" || {
  echo "REFUSING: no usable, funded deployer on $NET"; exit 1; }

cd "$ROOT"
echo "=== deploying (token $USDC, destination $DEST)"
OUT="$(mktemp)"
ROUTER_TOKEN="$USDC" ROUTER_DESTINATION="$DEST" \
  npx hardhat run scripts/deploy_usdc_router.ts --network "$NET" | tee "$OUT"

ROUTER="$(awk '/^router +:/ {print $3}' "$OUT")"
rm -f "$OUT"

echo
echo "=== verifying the DEPLOYED thing (read-only; no key needed)"
if [ -n "$ROUTER" ]; then
  ROUTER_ADDRESS="$ROUTER" ROUTER_DESTINATION="$DEST" \
    npx hardhat run scripts/verify_deployment.ts --network "$NET"
else
  echo "could not parse the router address — run the verifier manually with ROUTER_ADDRESS=0x…"
fi
