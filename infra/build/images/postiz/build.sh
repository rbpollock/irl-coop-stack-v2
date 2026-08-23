#!/usr/bin/env bash
# Build the irlcoop/postiz fork image from pinned upstream source + the fork patch.
#
# The fork (2026-08-22) adds three things over gitroomhq/postiz-app@74b01ad:
#   1. S3/MinIO storage backend — a STORAGE_ENDPOINT override (path-style +
#      configurable region) in cloudflare.storage.ts + r2.uploader.ts, so Postiz
#      can write media to the shared MinIO instead of the hardcoded Cloudflare R2.
#   2. Granular roles — Role enum extended with INVITER + OBSERVER (additive, no
#      data migration) and the member-management level map widened to match.
#   3. Zero-click SSO + skip onboarding — the login/register pages redirect to
#      the OIDC provider SERVER-SIDE (no login-page flicker), and GENERIC (SSO)
#      users skip the /launches onboarding wizard (group org + seat come from
#      the coop-api sync).
# The change set lives in irlcoop-fork.patch (a git diff of those 8 files).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
IMAGE="irlcoop/postiz:2026.08.3"
VERSION="2026.08.3"
PIN="74b01ada154a177242d558bedc646fcfed100adf"   # upstream commit the patch is against
PATCH="$ROOT/infra/build/images/postiz/irlcoop-fork.patch"
SRC="$(mktemp -d)/postiz-src"

echo "== postiz: cloning upstream @ $PIN ..."
# GitHub rejects `--branch <sha>` with `--depth 1`, so shallow-clone the default
# branch then fetch + checkout the pinned SHA.
git clone --depth 1 https://github.com/gitroomhq/postiz-app.git "$SRC"
git -C "$SRC" fetch --depth 1 origin "$PIN"
git -C "$SRC" checkout "$PIN"

echo "== postiz: applying irl.coop fork patch ..."
git -C "$SRC" apply "$PATCH"

echo "== postiz: building $IMAGE ..."
docker build -f "$SRC/Dockerfile.dev" -t "$IMAGE" \
  --build-arg NEXT_PUBLIC_VERSION="$VERSION" "$SRC"

echo "== postiz: built $IMAGE"
