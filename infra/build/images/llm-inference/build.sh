#!/usr/bin/env bash
# Build the llm-inference server image (llama.cpp server + our entrypoint).
# Thin by design: no model is baked in — weights live in the host model store
# (infra/instances/dev/data/models) and are bind-mounted at run time.
set -euo pipefail
TAG="${TAG:-irlcoop/llm-inference:0.1.0}"
cd "$(dirname "$0")"
docker build -t "$TAG" .
echo "built $TAG"