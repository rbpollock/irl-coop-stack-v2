#!/usr/bin/env bash
# Build the self-hosted embed+rerank inference server image.
# Models are baked in at build time (downloads ~1.4 GB), so this is slow the first run.
set -euo pipefail
TAG="${TAG:-irlcoop/embed-rerank:0.1.0}"
cd "$(dirname "$0")"
docker build -t "$TAG" .
echo "built $TAG"
