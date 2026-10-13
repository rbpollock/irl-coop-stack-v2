// Plane MCP server — exposes Plane's app API as MCP tools, acting AS THE MEMBER.
//
// The caller's coop JWT is forwarded straight through to Plane, whose
// CoopJWTAuthentication verifies it against coop-api's JWKS and maps `sub` to the
// member. Group scoping (`coop_group_scope`) is applied by Plane, so these tools
// see exactly what that member sees in the UI — there is no service credential
// here and no per-member session held server-side.
//
// Transport: a single JSON-RPC 2.0 POST /mcp endpoint (the same shape as the
// in-stack rag-api MCP server), plus GET /health for the container healthcheck.
import http from "node:http"

const PORT = Number(process.env.PORT || 8080)
const PLANE = (process.env.PLANE_URL || "https://plane.irl.coop").replace(/\/+$/, "")
const WS = process.env.PLANE_WORKSPACE || "coop-test"
const TIMEOUT_MS = Number(process.env.PLANE_TIMEOUT_MS || 15000)

const text = (v) => ({
  content: [{ type: "text", text: typeof v === "string" ? v : JSON.stringify(v, null, 2) }],
})

// Call Plane's app API as the member. The Authorization header IS the identity.
async function plane(auth, path, { method = "GET", body } = {}) {
  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort(), TIMEOUT_MS)
  try {
    const res = await fetch(`${PLANE}${path}`, {
      method,
      headers: {
        Authorization: auth,
        Accept: "application/json",
        ...(body ? { "Content-Type": "application/json" } : {}),
      },
      body: body ? JSON.stringify(body) : undefined,
      signal: ctrl.signal,
    })
    const raw = await res.text()
    let json = null
    try {
      json = JSON.parse(raw)
    } catch {
      /* non-JSON */
    }
    if (!res.ok) {
      const detail = (json && (json.detail || json.error)) || raw.slice(0, 200)
      throw new Error(`plane HTTP ${res.status}: ${detail}`)
    }
    return json ?? raw
  } finally {
    clearTimeout(timer)
  }
}

const rowsOf = (data) => (Array.isArray(data) ? data : data?.results ?? [])

const TOOLS = [
  {
    name: "list_projects",
    description:
      "List the Plane projects this member can see — the projects owned by coop groups they hold a seat in, plus any they are a direct project member of.",
    inputSchema: { type: "object", properties: {}, additionalProperties: false },
    handler: async (auth) => {
      const data = await plane(auth, `/api/workspaces/${WS}/projects/`)
      return text(
        rowsOf(data).map((p) => ({
          id: p.id,
          name: p.name,
          identifier: p.identifier,
          group_id: p.group_id ?? null,
          visibility: p.network,
        }))
      )
    },
  },
  {
    name: "list_work_items",
    description: "List the work items (issues) in one Plane project.",
    inputSchema: {
      type: "object",
      properties: {
        project_id: { type: "string", description: "Plane project UUID from list_projects" },
        limit: { type: "number", description: "max items to return (default 25, max 100)" },
      },
      required: ["project_id"],
      additionalProperties: false,
    },
    handler: async (auth, args) => {
      const pid = String(args?.project_id ?? "").trim()
      if (!pid) throw new Error("project_id is required")
      const data = await plane(auth, `/api/workspaces/${WS}/projects/${pid}/issues/`)
      const limit = Math.min(Number(args?.limit) || 25, 100)
      return text(
        rowsOf(data)
          .slice(0, limit)
          .map((i) => ({
            id: i.id,
            name: i.name,
            state: i.state_detail?.name ?? i.state ?? null,
            priority: i.priority ?? null,
            assignees: (i.assignee_ids ?? []).length,
          }))
      )
    },
  },
  {
    name: "create_issue",
    description:
      "Create a work item (issue) in a Plane project. The member must be able to act on the project — its coop groups' projects qualify at member level, exactly as they do for reading.",
    inputSchema: {
      type: "object",
      properties: {
        project_id: { type: "string", description: "Plane project UUID from list_projects" },
        name: { type: "string", description: "work item title" },
        description_html: { type: "string", description: "optional description (HTML)" },
        priority: {
          type: "string",
          enum: ["urgent", "high", "medium", "low", "none"],
          description: "optional priority",
        },
      },
      required: ["project_id", "name"],
      additionalProperties: false,
    },
    handler: async (auth, args) => {
      const pid = String(args?.project_id ?? "").trim()
      const name = String(args?.name ?? "").trim()
      if (!pid) throw new Error("project_id is required")
      if (!name) throw new Error("name is required")
      const payload = { name }
      if (args?.description_html) payload.description_html = String(args.description_html)
      if (args?.priority) payload.priority = String(args.priority)
      const created = await plane(auth, `/api/workspaces/${WS}/projects/${pid}/issues/`, {
        method: "POST",
        body: payload,
      })
      return text({
        created: true,
        id: created?.id ?? null,
        name: created?.name ?? name,
        project_id: pid,
      })
    },
  },
]

const toolsFor = () =>
  TOOLS.map(({ name, description, inputSchema }) => ({ name, description, inputSchema }))

function bearerOf(req) {
  const h = req.headers.authorization || ""
  return h.startsWith("Bearer ") ? h : null
}

async function dispatch(req, msg) {
  const id = msg?.id ?? null
  const ok = (result) => ({ jsonrpc: "2.0", id, result })
  const fail = (code, message) => ({ jsonrpc: "2.0", id, error: { code, message } })

  switch (msg?.method) {
    case "initialize":
      return ok({
        protocolVersion: "2025-03-26",
        capabilities: { tools: {} },
        serverInfo: { name: "plane-mcp", version: "0.1.0" },
      })
    case "notifications/initialized":
    case "ping":
      return ok({})
    case "tools/list":
      return ok({ tools: toolsFor() })
    case "tools/call": {
      const auth = bearerOf(req)
      if (!auth) return fail(-32001, "authentication required: a coop JWT Bearer token is needed")
      const tool = TOOLS.find((t) => t.name === msg.params?.name)
      if (!tool) return fail(-32602, `unknown tool: ${msg.params?.name ?? ""}`)
      try {
        return ok(await tool.handler(auth, msg.params?.arguments ?? {}))
      } catch (err) {
        return fail(-32000, String(err?.message ?? err))
      }
    }
    default:
      return fail(-32601, `method not found: ${msg?.method ?? ""}`)
  }
}

const server = http.createServer(async (req, res) => {
  if (req.method === "GET" && req.url === "/health") {
    res.writeHead(200, { "Content-Type": "application/json" })
    return res.end(JSON.stringify({ status: "ok", server: "plane-mcp", workspace: WS }))
  }
  if (req.method !== "POST" || !req.url?.startsWith("/mcp")) {
    res.writeHead(404, { "Content-Type": "application/json" })
    return res.end(JSON.stringify({ error: "not found" }))
  }
  let raw = ""
  for await (const chunk of req) raw += chunk
  let msg
  try {
    msg = JSON.parse(raw)
  } catch {
    res.writeHead(200, { "Content-Type": "application/json" })
    return res.end(JSON.stringify({ jsonrpc: "2.0", id: null, error: { code: -32700, message: "parse error" } }))
  }
  const reply = await dispatch(req, msg)
  res.writeHead(200, { "Content-Type": "application/json" })
  res.end(JSON.stringify(reply))
})

server.listen(PORT, "0.0.0.0", () => {
  console.log(`plane-mcp listening on :${PORT} (plane=${PLANE}, workspace=${WS})`)
})