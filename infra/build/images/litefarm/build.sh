#!/usr/bin/env bash
# Build the irlcoop/litefarm images from the irl.coop fork (rbpollock/LiteFarm).
#
# The fork branch `irl-coop-integration` carries the coop patch set:
#   - /gate_sso (fleet-gate SSO auto-login) + checkJwt/server.ts wiring
#   - farm.group_id migration (farm = group tenancy)
#   - eventEmit service -> coop-api /api/internal/events/ingest
#   - webapp: nginx.irlcoop.conf (SPA-only) + prod.irlcoop.Dockerfile (VITE_API_URL)
#
# Produces two images (LiteFarm natively splits SPA + API onto sibling domains):
#   - irlcoop/litefarm-api:<tag>  (node API, :5000)
#   - irlcoop/litefarm-web:<tag>  (nginx + built SPA, :80)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
TAG="2026.08.30"
PIN="e613fddb62c97d0232d4f22fd68b0c496489965c"  # irl-coop-integration commit (SSO + tenancy + events + auto-login + maps swap + click-to-populate + spinner + onChange + field-map MapLibre swap + null-guard + weather gateway + buildings/road names)
REPO="https://github.com/rbpollock/LiteFarm.git"
SRC="$(mktemp -d)/litefarm-src"

echo "== litefarm: cloning fork @ $PIN ..."
# GitHub rejects `--branch <sha>` with `--depth 1`; shallow-clone the default
# branch then fetch + checkout the pinned SHA.
git clone --depth 1 "$REPO" "$SRC"
git -C "$SRC" fetch --depth 1 origin "$PIN"
git -C "$SRC" checkout "$PIN"

echo "== litefarm: building API image (irlcoop/litefarm-api:$TAG) ..."
docker build -f "$SRC/packages/api/prod.Dockerfile" \
  -t "irlcoop/litefarm-api:$TAG" "$SRC/packages/"

echo "== litefarm: building web image (irlcoop/litefarm-web:$TAG) ..."
docker build -f "$SRC/packages/webapp/prod.irlcoop.Dockerfile" \
  -t "irlcoop/litefarm-web:$TAG" "$SRC/packages/"

echo "== litefarm: built irlcoop/litefarm-api:$TAG + irlcoop/litefarm-web:$TAG"
