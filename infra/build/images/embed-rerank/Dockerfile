FROM python:3.11-slim

WORKDIR /app

# build-essential: sentence-transformers/torch wheel install needs a compiler on slim.
RUN apt-get update && apt-get install -y --no-install-recommends build-essential && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

# Pre-download the models at build time so first start is instant and the image
# is a self-contained, reproducible artifact (no runtime network dependency).
ENV HF_HOME=/models TRANSFORMERS_CACHE=/models
RUN python -c "from sentence_transformers import SentenceTransformer, CrossEncoder; \
    SentenceTransformer('BAAI/bge-small-en-v1.5'); \
    CrossEncoder('BAAI/bge-reranker-v2-m3')"

EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
