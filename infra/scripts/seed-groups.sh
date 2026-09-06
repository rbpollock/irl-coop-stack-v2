#!/usr/bin/env bash
# Declarative seed groups: create any group whose slug is free + index open
# profiles into the RAG, then mark the "groups" RAG area public. Idempotent.
set -euo pipefail
ROOT=/home/service/development/irl-coop-stack-v2
cd "$ROOT"

echo "=== seed groups ==="
node infra/scripts/seed-groups.js

echo "=== mark 'groups' RAG area public ==="
docker exec storage-postgres-1 psql -U postgres -d rag -c \
  "UPDATE areas SET visibility='public' WHERE name='groups'" 2>&1

echo "=== seed complete ==="
