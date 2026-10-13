# plane-mcp — the Plane app API exposed as MCP tools, acting as the calling member.
#
# Deliberately dependency-free: Node's stdlib `fetch` + `http` are all the server
# needs (server.mjs), so there is no npm install and the image stays tiny. The
# member's coop JWT is forwarded to Plane, which verifies it against coop-api's
# JWKS and applies coop_group_scope — so no service credential and no per-member
# session live here.
FROM node:20-alpine

WORKDIR /app
COPY server.mjs ./

ENV PORT=8080
EXPOSE 8080

CMD ["node", "server.mjs"]