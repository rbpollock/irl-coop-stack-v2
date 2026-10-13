# rag-worker — provenance

**This source is ours.** Developed in-house (confirmed by the owner, 2026-10-13), not a
fork of an upstream project.

## Why it is here

`irlcoop/rag-worker` was built from a working tree that **never existed in this repository**:
no Dockerfile, no build script, no patch, and no provenance labels on the image. `CMD ["celery", "-A", "worker.celery_app.celery_app", "worker", ...]`.
It was one of the two images that could not be rebuilt from the repo at all
(`docs/IMAGE-PROVENANCE.md` §3 class C) — and container images are deliberately excluded
from the backup, on the assumption that they are rebuildable. For this image that
assumption was false, which is the hole this directory closes.

## The RAG ingestion worker — a Celery app (`src/worker/celery_app.py`,
`chunking.py`, `parsers.py`, `embeddings.py`, `db_types.py`), consuming queue work for
parsing/chunking/embedding.

## How it was recovered (2026-10-13)

Extracted from the deployed image, which is the only place the source existed:

```sh
docker create --name p irlcoop/rag-worker:0.1.0
docker cp p:/app vendor/rag-worker      # the built source, as shipped
docker rm -f p
```

`Dockerfile.irlcoop` was then reconstructed from the image's **own layer history**
(`docker history --no-trunc irlcoop/rag-worker:0.1.0`), so it reproduces the commands the
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
  of the image (`rag-worker` ships as hundreds of MB) and are re-downloadable; including them in
  the repository would add gigabytes for zero recovery value.

## Verified 2026-10-13 — recovered, recipe reconstructed, build NOT yet exercised

- Source recovered and vendored (468 KB; the 18.5 GB image is dependencies + model weights).
- `Dockerfile.irlcoop` reconstructed from the image's own layer history; its `CMD` names
  `worker.celery_app.celery_app`, which is in this tree.
- `requirements.lock.txt` pinned (211 packages) from the deployed image's pip freeze.
- **The build has not been run.** It installs the document-parsing stack (JRE + the Document AI
  dependencies) into a multi-GB image, and this host has ~25 GB free on `/` — an 18.5 GB build
  is not something to start casually. The recipe is in place; exercise it when there is room
  (or on `/mnt/storage`).
- Unlike `rag-api`, the **spec does not override this image's CMD** — `infra/instances/dev/apps/rag-worker.yaml`
  has no `command:`, so the image's own `CMD` is the real runtime path here.

## Build


```sh
docker build -t irlcoop/rag-worker:0.1.0 -f vendor/rag-worker/Dockerfile.irlcoop vendor/rag-worker
# then the deployed tag:
docker build -t irlcoop/rag-worker:0.1.0-1024 \
  -f infra/build/images/rag-embed/worker-overlay/Dockerfile \
  infra/build/images/rag-embed/worker-overlay
```
