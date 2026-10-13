# rag-api — provenance

**This source is ours.** Developed in-house (confirmed by the owner, 2026-10-13), not a
fork of an upstream project.

## Why it is here

`irlcoop/rag-api` was built from a working tree that **never existed in this repository**:
no Dockerfile, no build script, no patch, and no provenance labels on the image. `CMD ["langgraph", "dev", "--config", "langgraph.json", ...] — port 8000`.
It was one of the two images that could not be rebuilt from the repo at all
(`docs/IMAGE-PROVENANCE.md` §3 class C) — and container images are deliberately excluded
from the backup, on the assumption that they are rebuildable. For this image that
assumption was false, which is the hole this directory closes.

## The RAG service — a LangGraph application (`langgraph.json`, `agent.py`,
`src/app/{routes,services,core,db,auth,chat,evaluation}`), serving the retrieval and
MCP surface the dashboard's search reads.

## How it was recovered (2026-10-13)

Extracted from the deployed image, which is the only place the source existed:

```sh
docker create --name p irlcoop/rag-api:0.1.0
docker cp p:/app vendor/rag-api      # the built source, as shipped
docker rm -f p
```

`Dockerfile.irlcoop` was then reconstructed from the image's **own layer history**
(`docker history --no-trunc irlcoop/rag-api:0.1.0`), so it reproduces the commands the
shipping image was actually built from rather than describing them second-hand. It is
checkable against this tree: the image's `CMD` names a module that is present here.

## Reproducibility caveats — read before trusting a rebuild

- **Dependencies are not pinned.** The original build derived `requirements.txt` from
  `pyproject.toml` at build time (base deps plus the optional groups named in
  `INSTALL_OPTIONAL_GROUPS`) with **no version constraints**, so a rebuild today resolves
  current releases. That is how it was built — it is not a regression introduced here — but
  it means a rebuild is reproducible in *shape*, not byte-for-byte.
- **Two layered tags exist:** `0.1.0` (recovered here) and `0.1.0-1024`, built by the
  overlays in `infra/build/images/rag-embed/` on top of `0.1.0`. A rebuild of the deployed
  `-1024` tag is `vendor/` → `0.1.0` → overlay.
- **Not included, deliberately:** model weights and Python dependencies. They are the bulk
  of the image (`rag-api` ships as hundreds of MB) and are re-downloadable; including them in
  the repository would add gigabytes for zero recovery value.

## Build

```sh
docker build -t irlcoop/rag-api:0.1.0 -f vendor/rag-api/Dockerfile.irlcoop vendor/rag-api
# then the deployed tag:
docker build -t irlcoop/rag-api:0.1.0-1024 \
  -f infra/build/images/rag-embed/api-overlay/Dockerfile \
  infra/build/images/rag-embed/api-overlay
```
