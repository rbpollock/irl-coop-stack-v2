#!/bin/bash
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
docker build -t irlcoop/postgres-citus:12.1-vector-postgis "$DIR"
echo "built irlcoop/postgres-citus:12.1-vector-postgis"
