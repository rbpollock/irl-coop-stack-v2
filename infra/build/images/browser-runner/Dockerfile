# irlcoop/browser-runner — the fleet's browser execution unit.
# FROM the official Playwright image: node + chromium + deps pre-baked,
# no browser download, no npm dance. Two uses:
#   - dev/test harness: docker run irlcoop/browser-runner node /app/e2e/files-flow.mjs
#   - fleet runtime: Temporal activities dispatch ephemeral containers of
#     this image to run automations (the browser-management pillar);
#     the runner's spec contract (JSON inputs, evidence output) lands with
#     the Temporal activity slice.
# Build: ./build.sh  (stages the harnesses from apps/web/full-kit/e2e)
FROM mcr.microsoft.com/playwright:v1.46.0
WORKDIR /app
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1
COPY e2e/ /app/e2e/
COPY runner/ /app/runner/
# the base image ships the browsers at /ms-playwright but not a resolvable
# playwright package; pin the matching version, skip the browser download
# (already present)
RUN npm install --no-audit --no-fund --silent playwright@1.46.0
CMD ["node", "/app/runner/run.js"]
