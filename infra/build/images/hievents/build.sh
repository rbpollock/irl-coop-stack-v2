#!/usr/bin/env bash
# Build irlcoop/hievents-gate-sso — upstream Hi.Events + the irl.coop Gate SSO
# patch (same pattern as irlcoop/nocodb-gate-sso / formbricks-gate-sso /
# webstudio-builder-gate-sso).
#
# The patch (infra/instances/dev/assets/hievents/irlcoop-gate-sso.patch):
#   1. backend/app/Http/Actions/Auth/GateSsoAction.php — NEW: exchange the
#      oauth2-proxy gate identity (x-forwarded-email) for a Hi.Events JWT,
#      find-or-create the member + account. Guarded by a derived shared secret
#      and a loopback caller, so it can never mint a session for the public net.
#   2. backend/routes/api.php — GET /api/auth/gate-sso.
#   3. backend/config/app.php — the coop_gate_sso_* keys.
#   4. frontend/server.js — the SSR exchanges the gate header for the `token`
#      cookie on gated document routes (no password form for members).
#   5. frontend/src/components/routes/auth/Login/index.tsx — the primary
#      "Log in with irl.coop" door, with the native form kept as the fallback.
#   6. frontend/src/types.ts — the VITE_GATE_SSO_ENABLED config key.
#
# Usage:  bash infra/build/images/hievents/build.sh [tag]
#         (default tag: 1.11.1-beta — the version we run)
#
# ~20-40 min (yarn build + composer install). The clone is dropped in
# /home/service/build/hievents-src (persistent, NOT tmpfs).
set -euo pipefail

TAG="${1:-1.11.1-beta.2}"          # image tag (bump when the patch changes)
UPSTREAM_TAG="${UPSTREAM_TAG:-v1.11.1-beta}"   # upstream git tag to build from
IMAGE="irlcoop/hievents-gate-sso:${TAG}"
REPO_DIR="/home/service/build/hievents-src"
PATCH="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)/instances/dev/assets/hievents/irlcoop-gate-sso.patch"

if [ ! -f "${PATCH}" ]; then
  echo "patch not found: ${PATCH}" >&2
  exit 1
fi

if [ ! -d "${REPO_DIR}/.git" ]; then
  git clone https://github.com/HiEventsDev/Hi.Events "${REPO_DIR}"
fi

cd "${REPO_DIR}"
git fetch --tags --depth 1 origin "refs/tags/${UPSTREAM_TAG}:refs/tags/${UPSTREAM_TAG}" 2>/dev/null || git fetch --tags origin
git checkout --force "${UPSTREAM_TAG}"
# Start from a clean upstream tree every time: a previous patched run must not
# leave a half-applied state behind (reset drops staged leftovers, clean -fd
# drops untracked files while keeping ignored ones like node_modules).
git reset --hard "${UPSTREAM_TAG}"
git clean -fd >/dev/null

git apply "${PATCH}"
echo "applied $(basename "${PATCH}")"

docker build -f Dockerfile.all-in-one -t "${IMAGE}" .
echo "built ${IMAGE}"
