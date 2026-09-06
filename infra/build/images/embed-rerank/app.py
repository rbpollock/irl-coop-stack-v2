"""CPU inference server: self-hosted embeddings + rerank for the RAG retrieval pipeline.

Exposes the two contracts the deep-agent-rag-stack self-hosted providers expect:

- ``POST /v1/embeddings``  ``{"model": str, "input": [str, ...]}``
      -> ``{"object": "list", "model": str, "data": [{"object": "embedding", "index": i, "embedding": [float, ...]}, ...]}``
- ``POST /v1/rerank``      ``{"model": str, "query": str, "documents": [str, ...], "top_n": int|None}``
      -> ``{"results": [{"index": int, "score": float}, ...]}``  (sorted desc, truncated to top_n)

Both endpoints honour ``Authorization: Bearer <INFERENCE_API_KEY>`` when the key is
set; leave it empty to disable auth (dev only).

Models are loaded once at startup (CPU). Embedding dims default to 384
(bge-small-en-v1.5); set ``EMBED_MODEL`` to override.
"""

from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

EMBED_MODEL = os.environ.get("EMBED_MODEL", "BAAI/bge-small-en-v1.5")
RERANK_MODEL = os.environ.get("RERANK_MODEL", "BAAI/bge-reranker-v2-m3")
API_KEY = os.environ.get("INFERENCE_API_KEY", "")
RERANK_MAX_LENGTH = int(os.environ.get("RERANK_MAX_LENGTH", "512"))

app = FastAPI(title="irl.coop embed+rerank", version="0.1.0")

# Loaded lazily at startup; kept module-global for reuse across requests.
_embedder = None
_reranker = None


def _authorize(request: Request) -> None:
    """Reject requests missing the configured Bearer key (no-op when unset)."""
    if not API_KEY:
        return
    auth = request.headers.get("Authorization", "")
    if auth != f"Bearer {API_KEY}":
        raise HTTPException(status_code=401, detail="unauthorized")


@app.on_event("startup")
def _load_models() -> None:
    """Load embedding + rerank models once (CPU), keeping them warm for the lifetime."""
    global _embedder, _reranker
    from sentence_transformers import CrossEncoder, SentenceTransformer

    _embedder = SentenceTransformer(EMBED_MODEL)
    _reranker = CrossEncoder(RERANK_MODEL, max_length=RERANK_MAX_LENGTH)


class EmbedRequest(BaseModel):
    """OpenAI-compatible embeddings request."""

    model: str = ""
    input: list[str] | str


class RerankRequest(BaseModel):
    """RAG self-hosted rerank request."""

    model: str = ""
    query: str
    documents: list[str]
    top_n: int | None = None
    return_documents: bool = False
    normalize: bool = True


@app.post("/v1/embeddings")
def embeddings(req: EmbedRequest, request: Request) -> dict:
    """Embed a batch of texts; returns vectors in input order."""
    _authorize(request)
    texts = req.input if isinstance(req.input, list) else [req.input]
    vectors = _embedder.encode(texts, normalize_embeddings=True)
    return {
        "object": "list",
        "model": EMBED_MODEL,
        "data": [
            {"object": "embedding", "index": index, "embedding": [float(x) for x in vector]}
            for index, vector in enumerate(vectors)
        ],
    }


@app.post("/v1/rerank")
def rerank(req: RerankRequest, request: Request) -> dict:
    """Score documents against the query; returns sigmoid scores sorted desc."""
    _authorize(request)
    if not req.documents:
        return {"model": RERANK_MODEL, "results": []}
    pairs = [[req.query, doc] for doc in req.documents]
    scores = [float(score) for score in _reranker.predict(pairs)]
    results = [{"index": index, "score": score} for index, score in enumerate(scores)]
    results.sort(key=lambda item: -item["score"])
    if req.top_n is not None and req.top_n > 0:
        results = results[: req.top_n]
    return {"model": RERANK_MODEL, "results": results}


@app.get("/health")
def health() -> dict:
    """Liveness/readiness probe."""
    return {"status": "ok", "embed_model": EMBED_MODEL, "rerank_model": RERANK_MODEL}
