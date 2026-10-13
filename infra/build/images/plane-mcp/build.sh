#!/usr/bin/env bash
# Build the Plane MCP server image. Dependency-free by design (Node stdlib only),
# so this is a single-layer build with no npm install.
set -euo pipefail
TAG="${TAG:-irlcoop/plane-mcp:0.1.0}"
cd "$(dirname "$0")"
docker build -t "$TAG" .
echo "built $TAG"