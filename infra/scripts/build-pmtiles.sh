#!/bin/bash
# Build coverage.pmtiles (sovereign basemap) from the Geofabrik US extract.
# Runs Planetiler (docker) — download the PBF + build PMTiles in one pass.
#
# Output lives in a HOST build-scratch dir (/opt/app/storage/geo-data) — NOT
# infra/out/, because the declarative generator `shutil.rmtree`s infra/out/ on
# every run (it deleted a finished 9.9GB pmtiles once). Sources are cached in
# the same dir, so a re-run skips the ~12GB download.
#
#   GEO_DATA_DIR=/custom/path bash infra/scripts/build-pmtiles.sh
set -euo pipefail

DATA="${GEO_DATA_DIR:-/opt/app/storage/geo-data}"
mkdir -p "$DATA"

echo "== pulling planetiler image =="
docker pull ghcr.io/onthegomap/planetiler:latest

echo "== building coverage.pmtiles (download us-latest + build) =="
docker run --rm \
  -e JAVA_TOOL_OPTIONS="-Xmx32g" \
  -v "$DATA:/data" \
  ghcr.io/onthegomap/planetiler:latest \
  --download --area=us --output=/data/coverage.pmtiles --force

echo "== DONE =="
ls -lh "$DATA/coverage.pmtiles"
echo "next: upload to MinIO maps bucket (uv run --with minio python3 infra/scripts/upload-pmtiles.py)"
