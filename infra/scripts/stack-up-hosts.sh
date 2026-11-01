#!/usr/bin/env bash
# Host source apps — the three `type: source` apps with NO docker-compose, which
# stack-up.sh skips ("no docker compose — host process"). These run as host
# processes routed by Traefik's file provider to 172.17.0.1:<port>:
#   web     :3000  (Next.js)   apps/web/irl-dashboard
#   coop-api:3001  (Fastify)   apps/coop-api
#   rail    :3010  (Fastify)   apps/peer_xyz_payments
#   hardhat :8545  (local chain) contracts
#
# Idempotent: an app is started only if it isn't already answering on its port.
# A freshly-started hardhat node gets the Safe contracts deployed (deterministic
# CREATE2 addresses) — skipped if the singleton already has code.
set -u

LOCKFILE="/tmp/stack-up-hosts.lock"
exec 200>"$LOCKFILE"
flock -n 200 || { printf 'stack-up-hosts.sh already running\n' >&2; exit 1; }
echo $$ >&200

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LOGDIR="$ROOT/.logs"
mkdir -p "$LOGDIR"

say()  { printf '\033[1;34m== %s\033[0m\n' "$*"; }
ok()   { printf '  \033[32mOK\033[0m   %s\n' "$*"; }
warn() { printf '  \033[33mWARN\033[0m %s\n' "$*"; }

NVM='[ -s "$HOME/.nvm/nvm.sh" ] && . "$HOME/.nvm/nvm.sh"'

# health PORT — 0 if answering (JSON-RPC for 8545, plain HTTP otherwise)
health() {
  local port="$1" path="${2:-/}"
  if [ "$port" = "8545" ]; then
    curl -sf -m 3 -X POST -H 'Content-Type: application/json' \
      --data '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}' \
      "http://127.0.0.1:$port" >/dev/null 2>&1
  else
    curl -sf -o /dev/null -m 5 "http://127.0.0.1:$port$path"
  fi
}

# start NAME PORT DIR CMD [ARGS...] — starts if not answering; returns 0 if
# already up, 1 if it just started (caller may need to post-provision).
start() {
  local name="$1" port="$2" path="$3" dir="$4"; shift 4
  if health "$port" "$path"; then
    ok "$name already up (:$port)"
    return 0
  fi
  say "starting $name (:$port)"
  ( cd "$ROOT/$dir" && eval "$NVM" && setsid nohup "$@" </dev/null >>"$LOGDIR/$name.log" 2>&1 & )
  return 1
}

say "host source apps"

# web — webpack dev server (NOT --turbopack: the 15.2.8 turbopack dev server is
# flaky under hot-reload and wedges on :3000 — bound but never answering).
pkill -f 'next.*dev' 2>/dev/null || true
start web 3000 / apps/web/irl-dashboard npx next dev

# coop-api — ts-node-dev Fastify (dotenv: .env then infra/out/dev/secrets.env).
# Use ts-node (NOT ts-node-dev --respawn) to avoid orphan wrapper processes on restart.
pkill -f 'ts-node.*server\.ts' 2>/dev/null || true
start coop-api 3001 /api/auth/config apps/coop-api npx ts-node --transpile-only src/server.ts

# peer_xyz_payments — the payment rail service (internal only; no proxy route).
pkill -f 'ts-node.*peer_xyz_payments' 2>/dev/null || true
start peer_xyz_payments 3010 /health apps/peer_xyz_payments npx ts-node --transpile-only src/server.ts

# treasury-relayer — the off-chain proof gate for the shielded pool.
pkill -f 'ts-node.*treasury-relayer' 2>/dev/null || true
start treasury-relayer 3020 /health apps/treasury-relayer npx ts-node --transpile-only src/server.ts

# hardhat — local chain + Safe contract deploy on a fresh node.
if start hardhat 8545 / contracts npx hardhat node; then
  ok "hardhat already up — contracts assumed deployed"
else
  for _ in $(seq 1 20); do health 8545 && break; sleep 1; done
  SINGLETON="$(grep -E 'SAFE_SINGLETON_ADDRESS' "$ROOT/infra/instances/dev/apps/coop-api.yaml" \
    | grep -oE '0x[0-9a-fA-F]{40}' | head -1)"
  CODE="$(curl -sf -m 3 -X POST -H 'Content-Type: application/json' \
    --data "{\"jsonrpc\":\"2.0\",\"method\":\"eth_getCode\",\"params\":[\"$SINGLETON\",\"latest\"],\"id\":1}" \
    http://127.0.0.1:8545 2>/dev/null)"
  if printf '%s' "$CODE" | grep -q '"result":"0x"'; then
    say "deploying Safe contracts (fresh node)"
    ( cd "$ROOT/contracts" && eval "$NVM" \
      && npx hardhat run scripts/deploy_local.ts --network local >>"$LOGDIR/hardhat.log" 2>&1 )
    ok "contracts deployed"
  else
    ok "Safe contracts already deployed"
  fi
fi

# temporal worker — the durable lane (delivery/digest/postiz-sync sweeps). Not an
# HTTP server, so no port health check; pgrep for the ts-node worker process.
if pgrep -f 'ts-node src/temporal/worker.ts' >/dev/null 2>&1; then
  ok "temporal worker already up"
else
  say "starting temporal worker"
  ( cd "$ROOT/apps/coop-api" && eval "$NVM" && setsid nohup npm run worker </dev/null >>"$LOGDIR/temporal-worker.log" 2>&1 & )
  ok "temporal worker started"
fi

echo
printf 'logs: %s/{web,coop-api,hardhat,temporal-worker}.log\n' "$LOGDIR"
