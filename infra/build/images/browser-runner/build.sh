#!/usr/bin/env bash
# Build irlcoop/browser-runner — stage the harnesses (the e2e dir lives in
# the full-kit workspace, not in the image context) into infra/out
# (gitignored), then docker build.
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$DIR/../../../.." && pwd)"
STAGE="$ROOT/infra/out/browser-runner"

rm -rf "$STAGE"
mkdir -p "$STAGE/e2e" "$STAGE/runner"
cp "$DIR/Dockerfile" "$STAGE/"
cp "$ROOT/apps/web/full-kit/e2e/"*.mjs "$STAGE/e2e/"
cp "$DIR/runner/"*.js "$STAGE/runner/"

docker build -t irlcoop/browser-runner:latest "$STAGE"
echo "built irlcoop/browser-runner:latest"
