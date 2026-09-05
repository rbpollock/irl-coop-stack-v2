# irlcoop/postgres-citus:12.1-vector-postgis — Citus 12.1 with pgvector + PostGIS.
# Byte-compatible with citusdata/citus:12.1 (PostgreSQL 16 base).
FROM citusdata/citus:12.1

RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-16-pgvector \
    postgresql-16-postgis-3 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
