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
shipping image was actually built from rather than describing them second-hand. It is checkable against this tree: the image's `CMD` names a module that is present
here, and it reproduces byte-for-byte (`langgraph dev --config langgraph.json --host
0.0.0.0 --port 8000 --no-browser --no-reload`).

**Base image, identified by evidence:** `python:3.12-slim` (Debian 13 trixie, Python
3.12.14). Verified by probing the deployed image — `gcc`, `git`, `make`, `curl` and `vim`
are all ABSENT (the full image retains buildpack-deps tooling). A first rebuild used full
`python:3.12` and came out 2.34 GB against the deployed 906 MB; the slim base is what
reproduces the size.

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

## Verified 2026-10-13 — it builds **and runs**

| Check | Result |
|---|---|
| Builds from this directory | yes — `docker build -t irlcoop/rag-api:0.1.0 -f vendor/rag-api/Dockerfile.irlcoop vendor/rag-api` |
| Size vs deployed | **906 MB — identical** to `irlcoop/rag-api:0.1.0` (the unpinned build came out 930 MB) |
| Runs the way production runs it | yes — `Up`, `Application startup complete` |
| HTTP | `/`, `/docs`, `/health`, `/openapi.json` all **200**, matching the deployed control run side by side |
| CMD fidelity | byte-identical to the deployed image's CMD |

### The finding that made the difference: unpinned dependencies are not a formality

The first rebuild (no lock) **built fine and could not start**:

```
ModuleNotFoundError: No module named 'psycopg'
  sqlalchemy/dialects/postgresql/psycopg.py, line 497, in import_dbapi
```

The original build installed **SQLAlchemy 2.0.52**; today's unpinned resolution installs
**2.1.4**, and 2.1 switches the default `postgresql://` driver from psycopg2 to **psycopg v3**,
which this image does not ship. Installing from `requirements.lock.txt` — pinned from the
deployed image's own `pip freeze` — reproduces a 906 MB image that runs and answers 200s.

**Lesson: pin from a known-good *running image*, not from a manifest.** This lock exists only
because the deployed image was still on the host to be frozen.

### And the CMD is a decoy

The image's baked `CMD` is `langgraph dev ...`, but that is **not how the service runs** — the
deploy command comes from `infra/instances/dev/apps/rag-api.yaml`:

    uvicorn app.main:app --host 0.0.0.0 --port 8000

Running the image's own CMD fails in *both* the deployed and the rebuilt image (the langgraph
dev server wants to load the custom HTTP app and needs env the image does not carry). So a bare
`docker run` of this image is not a health check — verify it the way the stack runs it.

## Build

```sh
docker build -t irlcoop/rag-api:0.1.0 -f vendor/rag-api/Dockerfile.irlcoop vendor/rag-api
# then the deployed tag:
docker build -t irlcoop/rag-api:0.1.0-1024 \
  -f infra/build/images/rag-embed/api-overlay/Dockerfile \
  infra/build/images/rag-embed/api-overlay
```
