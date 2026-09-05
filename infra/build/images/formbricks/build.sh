#!/usr/bin/env bash
# Build the irlcoop/formbricks-gate-sso image from pinned upstream source + the
# coop gate-SSO patch (same pattern as nocodb-gate-sso / webstudio-builder-gate-sso).
#
# The patch (irlcoop-fork.patch, against formbricks 5.4.0) adds:
#   1. proxy.ts middleware  — when GATE_SSO_ENABLED=1 and x-forwarded-email is
#      present on the admin domain, redirect to /api/auth/gate-sso instead of the
#      native /auth/login form.
#   2. app/api/auth/gate-sso/route.ts — find-or-create the member by email, mint a
#      Better Auth session (prisma.session row + the signed
#      __Secure-formbricks.session_token cookie), redirect.
#   3. lib/env.ts — the GATE_SSO_ENABLED flag (opt-in, off unless "1").
#
# Formbricks SSO (OIDC/Keycloak/SAML) is Enterprise-licensed and phone-homes to
# ee.formbricks.com, so this gate is the sovereign SSO path (oauth2-proxy →
# coop-api OIDC → x-forwarded-email → auto-login). Survey respondents stay
# anonymous on the PUBLIC_URL domain (not gated).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
IMAGE="irlcoop/formbricks-gate-sso:5.4.0"
PIN="286958e36464663489bfbc73d87abbd0f573825f"   # the 5.4.0 tag commit
PATCH="$ROOT/infra/build/images/formbricks/irlcoop-fork.patch"
SRC="$(mktemp -d)/formbricks-src"

echo "== formbricks: cloning upstream @ $PIN ..."
git clone --depth 1 https://github.com/formbricks/formbricks.git "$SRC"
git -C "$SRC" fetch --depth 1 origin "$PIN"
git -C "$SRC" checkout "$PIN"

echo "== formbricks: applying irl.coop gate-SSO patch ..."
git -C "$SRC" apply "$PATCH"

echo "== formbricks: building $IMAGE ..."
# The fork patch drops the Dockerfile's --mount=type=secret clauses (this host's
# legacy docker builder lacks --secret); read-secrets.sh supplies placeholder
# build-time defaults and real values come from env at runtime.
docker build -f "$SRC/apps/web/Dockerfile" -t "$IMAGE" "$SRC"

echo "== formbricks: built $IMAGE"
