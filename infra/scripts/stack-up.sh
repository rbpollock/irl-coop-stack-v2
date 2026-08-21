#!/usr/bin/env bash
# irl.coop stack bring-up — every declared project, idempotent.
#
#  1. Every pillar compose in the generated tree (infra/out/dev/compose/*/)
#  2. Every `type: source` app (its own compose, e.g. plane)
#
# Each project is `docker compose up -d` (restart policies then hold it).
# Writes a declared-vs-running snapshot to $STACK_REPORT and prints it.
# Exits nonzero if any project failed to come up, so a systemd unit running
# this lands in a visible `failed` state — that IS the error flag.
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT="$ROOT/infra/out/dev"
REPORT="${STACK_REPORT:-/var/lib/irl-coop/stack-status.json}"
FAILED=0
FAILED_NAMES=""

say()  { printf '\033[1;34m== %s\033[0m\n' "$*"; }
ok()   { printf '  \033[32mOK\033[0m  %s\n' "$*"; }
fail() { printf '  \033[31mFAIL\033[0m %s\n' "$*"; FAILED=1; FAILED_NAMES="${FAILED_NAMES:+$FAILED_NAMES, }$*"; }
warn() { printf '  \033[33mWARN\033[0m %s\n' "$*"; }

command -v docker >/dev/null || { fail "docker not found"; exit 1; }

# Check and build missing custom images before bringing up pillars
missing_images=0
for img in "irlcoop/element-web:v1.12.18" "irlcoop/synapse-s3:v1.118.0" "irlcoop/postgres-citus:12.1-vector" "irlcoop/browser-runner:latest"; do
  if ! docker image inspect "$img" >/dev/null 2>&1; then
    missing_images=1
    break
  fi
done

if [ "$missing_images" = "1" ]; then
  say "Detected missing custom images. Building them first..."
  if [ -f "$ROOT/infra/scripts/build-images.sh" ]; then
    bash "$ROOT/infra/scripts/build-images.sh"
  else
    fail "build-images.sh not found under $ROOT/infra/scripts/"
  fi
fi

# 1. Generated pillar composes (proxy, authentication, storage, cache, ...)
for pillar_dir in "$OUT"/compose/*/; do
  [ -d "$pillar_dir" ] || continue
  pillar="$(basename "$pillar_dir")"
  base="$pillar_dir/docker-compose.yml"
  [ -f "$base" ] || continue
  files=(-f "$base")
  [ -f "$pillar_dir/docker-compose.override.yml" ] && files+=(-f "$pillar_dir/docker-compose.override.yml")
  say "pillar: $pillar"
  if docker compose "${files[@]}" up -d >/dev/null 2>&1; then
    ok "$pillar up"
  else
    fail "$pillar up failed"
  fi
done

# 2. Source apps (spec type: source → their own compose)
say "source apps"
for spec in "$ROOT"/infra/instances/dev/apps/*.yaml; do
  [ -f "$spec" ] || continue
  type="$(grep -E '^type:' "$spec" | awk '{print $2}')"
  [ "$type" = "source" ] || continue
  name="$(grep -E '^name:' "$spec" | awk '{print $2}')"
  src="$(grep -E '^source:' "$spec" | awk '{print $2}')"
  src="$(cd "$ROOT" && echo "$src")"   # resolve relative to the repo root
  if [ -f "$src/docker-compose.yml" ]; then
    if docker compose -f "$src/docker-compose.yml" up -d >/dev/null 2>&1; then
      ok "$name up"
    else
      fail "$name up failed"
    fi
  else
    printf '  \033[2mSKIP\033[0m %s (no docker compose — host process)\n' "$name"
  fi
done

# 3. Host source apps (web, coop-api, hardhat) — the SKIPped no-compose apps,
# launched directly by stack-up-hosts.sh (idempotent + health-checked).
say "host source apps"
if bash "$ROOT/infra/scripts/stack-up-hosts.sh"; then
  ok "host apps handled"
else
  warn "host apps bring-up reported an issue"
fi

# 4. Snapshot for motd / operators
say "snapshot"
if python3 "$ROOT/infra/scripts/stack-report.py" --json "$REPORT"; then
  ok "report -> $REPORT"
else
  warn "report generation failed"
fi
echo
python3 "$ROOT/infra/scripts/stack-report.py" 2>/dev/null || true
echo
if [ "$FAILED" = "1" ]; then
  printf '\033[31mSTACK BRING-UP INCOMPLETE: %s\033[0m\n' "$FAILED_NAMES"
  exit 1
fi
printf '\033[32mSTACK UP — all declared projects running.\033[0m\n'
