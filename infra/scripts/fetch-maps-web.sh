#!/bin/bash
# Populate the durable maps web root (/opt/app/storage/geo-data/web/) served by
# the `maps` nginx app (maps.irl.coop): index.html + client libs + self-hosted
# Noto glyphs. Idempotent. Run after changing infra/scripts/map-embed.html or
# bumping the pinned lib versions.
#
# Glyph source is MapLibre's own demotiles font host (NOT fonts.openmaptiles.org,
# which serves a single 2.7KB placeholder for every range). 256 ranges x 2
# fontstacks = 512 PBF files, ~5MB total.
set -euo pipefail

SUDO_PASSWORD="$(grep -E '^SUDO_PASSWORD=' /home/service/.hermes/.env | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'")"
WEB=/opt/app/storage/geo-data/web
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# The parent is root-owned (Planetiler runs as root) — create + own the web dir.
echo "$SUDO_PASSWORD" | sudo -S bash -c "mkdir -p '$WEB/glyphs' && chown -R service:service '$WEB'"

# 1. index.html (versioned source in the repo)
cp "$SCRIPT_DIR/map-embed.html" "$WEB/index.html"

# 2. client libs (pinned) — copy from the self-hosted MinIO maps bucket
curl -fsSL -o "$WEB/maplibre-gl.js"  "https://s3api.irl.coop/maps/maplibre-gl.js"
curl -fsSL -o "$WEB/maplibre-gl.css" "https://s3api.irl.coop/maps/maplibre-gl.css"
curl -fsSL -o "$WEB/pmtiles.js"      "https://s3api.irl.coop/maps/pmtiles.js"

# 3. Noto glyphs (MapLibre demotiles) — the fontstacks the style references
for stack in "Noto Sans Regular" "Noto Sans Bold"; do
  mkdir -p "$WEB/glyphs/$stack"
  got=0
  for i in $(seq 0 255); do
    s=$((i * 256)); e=$((s + 255))
    f="$s-$e.pbf"
    if curl -fsSL -o "$WEB/glyphs/$stack/$f" \
        "https://demotiles.maplibre.org/font/${stack// /%20}/$f"; then
      got=$((got + 1))
    fi
  done
  echo "  $stack: $got/256 ranges"
done

echo "done — $(find "$WEB" -type f | wc -l) files, $(du -sh "$WEB" | cut -f1)"
