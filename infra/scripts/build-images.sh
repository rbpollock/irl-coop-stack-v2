#!/usr/bin/env bash
# irl.coop custom docker images builder — canonical builder for local images.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

say() { printf '\033[1;34m== %s\033[0m\n' "$*"; }
ok()  { printf '  \033[32mOK\033[0m  %s\n' "$*"; }

say "building custom stack images"

# 1. element-web
if [ -d "$ROOT/infra/build/images/element-web" ]; then
  say "building element-web..."
  docker build -t irlcoop/element-web:v1.12.18 "$ROOT/infra/build/images/element-web" >/dev/null
  ok "element-web built"
fi

# 2. synapse-s3
if [ -d "$ROOT/infra/build/images/synapse-s3" ]; then
  say "building synapse-s3..."
  docker build -t irlcoop/synapse-s3:v1.118.0 "$ROOT/infra/build/images/synapse-s3" >/dev/null
  ok "synapse-s3 built"
fi

# 3. postgres-citus (vector)
if [ -f "$ROOT/infra/build/images/postgres-citus/build.sh" ]; then
  say "building postgres-citus..."
  bash "$ROOT/infra/build/images/postgres-citus/build.sh" >/dev/null
  ok "postgres-citus built"
fi

# 4. browser-runner
if [ -f "$ROOT/infra/build/images/browser-runner/build.sh" ]; then
  say "building browser-runner..."
  bash "$ROOT/infra/build/images/browser-runner/build.sh" >/dev/null
  ok "browser-runner built"
fi

# 5. postiz (irl.coop fork — S3/MinIO + granular roles)
if [ -f "$ROOT/infra/build/images/postiz/build.sh" ]; then
  say "building postiz (irl.coop fork)..."
  bash "$ROOT/infra/build/images/postiz/build.sh"
  ok "postiz built"
fi

say "All custom images built and ready!"
