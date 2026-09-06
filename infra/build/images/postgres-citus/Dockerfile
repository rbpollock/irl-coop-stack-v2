# irlcoop/postgres-citus:12.1-vector-postgis-pgroonga — Citus 12.1 with
# pgvector + PostGIS + PGroonga (Traditional-Chinese full-text for the RAG stack).
# Byte-compatible with citusdata/citus:12.1 (PostgreSQL 16 base, PGDG).
FROM citusdata/citus:12.1

RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-16-pgvector \
    postgresql-16-postgis-3 \
    ca-certificates curl gnupg lsb-release \
    && curl -fsSL -o /tmp/groonga.deb \
       https://packages.groonga.org/debian/groonga-apt-source-latest-bookworm.deb \
    && apt-get install -y /tmp/groonga.deb \
    && rm -f /tmp/groonga.deb \
    && apt-get update \
    && apt-get install -y --no-install-recommends postgresql-16-pgdg-pgroonga \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
