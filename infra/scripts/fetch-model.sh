#!/usr/bin/env bash
# fetch-model.sh — download a model file into the instance model store.
#
# Models are DATA, not code: kept once on the host and bind-mounted read-only
# into inference containers (llm-inference mounts it at /models), so an image
# rebuild never re-downloads weights and the same store backs several containers.
# The store lives under the instance tree (infra/instances/<inst>/data/models),
# which is gitignored — big weights never enter the repo.
#
# The download runs in a container that mounts the store: the instance `data/`
# dir is root-owned (containers create it) and the host user cannot write there,
# so bind-mounting sidesteps host permissions entirely — the same reason the
# store is container-bound data in the first place. Uses the llama.cpp server
# image (already present, ships curl + sh); no extra image is pulled.
#
# Usage:
#   infra/scripts/fetch-model.sh <hf-repo> <file> [instance]
#   infra/scripts/fetch-model.sh Qwen/Qwen2.5-3B-Instruct-GGUF qwen2.5-3b-instruct-q4_k_m.gguf
#
# A symlink `model.gguf` is left pointing at the last fetched file, which is the
# entrypoint's default MODEL_PATH.
set -euo pipefail

REPO="${1:?usage: fetch-model.sh <hf-repo> <file> [instance]}"
FILE="${2:?usage: fetch-model.sh <hf-repo> <file> [instance]}"
INSTANCE="${3:-dev}"

STORE="$(cd "$(dirname "$0")/.." && pwd)/instances/${INSTANCE}/data/models"
URL="https://huggingface.co/${REPO}/resolve/main/${FILE}?download=true"
IMAGE="${IMAGE:-ghcr.io/ggml-org/llama.cpp:server}"

echo "→ ${URL}"
docker run --rm \
  -v "${STORE}:/models" \
  -e "FILE=${FILE}" -e "URL=${URL}" \
  --entrypoint sh "$IMAGE" -c '
    set -e
    if [ -f "/models/$FILE" ]; then
      echo "already present: /models/$FILE"
    else
      # .part + move, so a half-download is never mistaken for a usable model.
      curl -fSL --retry 3 -o "/models/$FILE.part" "$URL"
      mv "/models/$FILE.part" "/models/$FILE"
    fi
    ln -sfn "$FILE" /models/model.gguf
    ls -lh "/models/$FILE" /models/model.gguf
  '

echo "store: ${STORE}  (model.gguf -> ${FILE})"