# llm-inference — self-hosted CPU chat generation (llama.cpp `llama-server`), the
# coop-run fallback tier for the dashboard chat / MCP harness.
#
# This image is deliberately THIN: the official llama.cpp server image plus our
# entrypoint. The MODEL is NOT baked in — models are data, not code: kept once in
# the host model store (infra/instances/dev/data/models) and bind-mounted
# read-only at /models (see the app spec). A rebuild therefore never re-downloads
# weights, and the same store can back other inference containers without
# duplication. Populate it with infra/scripts/fetch-model.sh.
FROM ghcr.io/ggml-org/llama.cpp:server

COPY entrypoint.sh /usr/local/bin/llm-entrypoint.sh
RUN chmod +x /usr/local/bin/llm-entrypoint.sh

EXPOSE 8080
ENTRYPOINT ["/usr/local/bin/llm-entrypoint.sh"]