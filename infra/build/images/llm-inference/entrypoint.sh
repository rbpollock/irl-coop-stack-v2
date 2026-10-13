#!/bin/sh
# Serve the model from the bind-mounted store over the OpenAI-compatible
# /v1/chat/completions surface. Threads default to every core; the Bearer key
# comes from INFERENCE_API_KEY (empty = auth disabled — dev only). Jinja
# templating is on by default, which makes the model's chat template (and tool
# calls) work.
set -e

MODEL="${MODEL_PATH:-/models/model.gguf}"
THREADS="${LLAMA_THREADS:-$(nproc)}"
CTX="${LLAMA_CTX:-8192}"

if [ ! -f "$MODEL" ]; then
  echo "llm-inference: no model at $MODEL" >&2
  echo "  populate the store: infra/scripts/fetch-model.sh <hf-repo> <file>" >&2
  exit 1
fi

set -- -m "$MODEL" --host 0.0.0.0 --port 8080 \
  -c "$CTX" -t "$THREADS" -a irl-coop-fallback --no-webui

if [ -n "${INFERENCE_API_KEY:-}" ]; then
  set -- "$@" --api-key "$INFERENCE_API_KEY"
fi

exec /app/llama-server "$@"