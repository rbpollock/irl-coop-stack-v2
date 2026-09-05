#!/usr/bin/env python3
"""Upload coverage.pmtiles (from the build scratch dir) to the MinIO maps bucket.

Run with:  uv run --with minio python3 infra/scripts/upload-pmtiles.py

MinIO does NOT implement the S3 PutBucketCors API (returns 501) — cross-origin
tile fetch is configured via MINIO_API_CORS_ALLOW_ORIGIN in the minio app spec,
not here. This script only uploads the file with an immutable cache header.
"""
import os
from minio import Minio

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.environ.get("GEO_DATA_DIR", "/opt/app/storage/geo-data") + "/coverage.pmtiles"


def load_secret(name):
    with open(os.path.join(REPO, "infra/out/dev/secrets.env")) as f:
        for line in f:
            line = line.strip()
            if line.startswith(f"{name}="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit(f"{name} not found")


client = Minio("127.0.0.1:9000", access_key="minioadmin",
               secret_key=load_secret("MINIO_ROOT"), secure=False)

print(f"uploading {SRC} ...")
client.fput_object(
    "maps", "coverage.pmtiles", SRC,
    content_type="application/octet-stream",
    metadata={"Cache-Control": "public, max-age=31536000, immutable"},
    part_size=100 * 1024 * 1024,
)
print("uploaded")

st = client.stat_object("maps", "coverage.pmtiles")
print(f"stat: {st.size} bytes, {st.content_type}")
print("done -> https://s3api.irl.coop/maps/coverage.pmtiles")
