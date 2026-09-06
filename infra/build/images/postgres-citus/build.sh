#!/bin/bash
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TAG="${1:-12.1-vector-postgis-pgroonga}"
docker build -t "irlcoop/postgres-citus:${TAG}" "$DIR"
echo "built irlcoop/postgres-citus:${TAG}"
