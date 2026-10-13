# vendor/ — source we own, kept in the monorepo

Upstream code we have patched or written is fetched at build time, which means the build
depends on someone else's git host continuing to serve a specific commit. This directory is
where that dependency is retired.

| Directory | What | Status |
|---|---|---|
| `rag-api/` | our in-house LangGraph RAG service | recovered from the deployed image 2026-10-13 (`PROVENANCE.md`) |
| `rag-worker/` | our in-house Celery ingestion worker | recovered from the deployed image 2026-10-13 (`PROVENANCE.md`) |

## The rules for anything added here

1. **One squashed commit** of the upstream tree at the pinned SHA — never upstream history
   (history is what makes a vendored fork enormous).
2. **A `Dockerfile.irlcoop` at the vendor root**, so the build is
   `docker build vendor/<app>` with **no network**.
3. **Exclude** build outputs, fixtures, and anything re-downloadable — model weights above
   all.
4. **`git-lfs` for any blob over ~10 MB** (GitHub hard-rejects >100 MB).
5. **Our change stays legible**: the original `*.patch` stays in
   `infra/build/images/<app>/` as the human-readable record of what we changed.
6. **Record the pin** in `infra/build/images/manifest.yaml`.

See `docs/IMAGE-PROVENANCE.md` for the full classification and the reasoning.
