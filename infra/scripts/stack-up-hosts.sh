#!/usr/bin/env bash
# Host source apps — the three `type: source` apps with NO docker-compose, which
# stack-up.sh skips ("no docker compose — host process"). These run as host
# processes routed by Traefik's file provider to 172.17.0.1:<port>:
#   web     :3000  (Next.js)   apps/web/irl-dashboard
#   coop-api:3001  (Fastify)   apps/coop-api
#   hardhat :8545  (local chain) contracts
#
# Idempotent: an app is started only if it isn't already answering on its port.
# A freshly-started hardhat node gets the Safe contracts deployed (deterministic
# CREATE2 addresses) — skipped if the singleton already has code.
set -u

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
  ( cd "$ROOT/$dir" && eval "$NVM" && nohup "$@" </dev/null >>"$LOGDIR/$name.log" 2>&1 & )
  return 1
}

say "host source apps"

# web — webpack dev server (NOT --turbopack: the 15.2.8 turbopack dev server is
# flaky under hot-reload and wedges on :3000 — bound but never answering).
start web 3000 / apps/web/irl-dashboard npx next dev

# coop-api — ts-node-dev Fastify (dotenv: .env then infra/out/dev/secrets.env).
start coop-api 3001 /api/auth/config apps/coop-api npm run dev

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

echo
printf 'logs: %s/{web,coop-api,hardhat}.log\n' "$LOGDIR"
