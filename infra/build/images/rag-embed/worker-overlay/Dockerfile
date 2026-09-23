# Rag worker overlay: only the embedding-dimension constant changes.
# Base ships the full deep-agent-worker source; we override the one file that
# pins DEFAULT_EMBEDDING_DIMENSIONS to 1024 (was 1536) to support a self-hosted
# local embedder (bge-large-en-v1.5, 1024-dim) instead of a 1536-dim one.
FROM irlcoop/rag-worker:0.1.0
COPY src /app/src