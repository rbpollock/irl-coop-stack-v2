// MCP aggregator/proxy — a Model Context Protocol endpoint (streamable-HTTP
// shape, JSON-RPC 2.0 over POST) that exposes coop-api's own capabilities as
// MCP tools, scoped by the caller's coop JWT, and aggregates/forwards to
// upstream MCP servers (e.g. the deep-agent-rag-stack knowledgebase).
//
// Auth: the caller presents the same Bearer coop JWT the dashboard holds
// (verifyBearer → sub). Tool listing is grant-filtered; every local tool runs
// inside withIdentity(sub) so Postgres RLS scopes it to the caller's seats.
//
// The client-side inference engine (a local model on a member's device) talks
// to this endpoint over HTTPS — it holds the coop JWT, sends JSON-RPC, gets
// back tool results. No LLM tokens stream through here; this is tools only.

import { FastifyInstance } from "fastify"
import { verifyBearer } from "./verify-jwt"
import { getGroupSeats, getRolesAndGrants, withIdentity } from "./db"

type McpTool = {
  name: string
  description: string
  inputSchema: Record<string, unknown>
  grant?: string // capability required to LIST + CALL (undefined = any authed member)
  handler: (sub: string, args: any) => Promise<unknown>
  upstream?: { name: string; url: string } // set for proxied tools
}

// ---- local tools (read-only first slice; write tools + grants come next) ----

const LOCAL_TOOLS: McpTool[] = [
  {
    name: "list_my_groups",
    description: "List the coop groups the caller holds a seat in (slug, name, roles).",
    inputSchema: { type: "object", properties: {} },
    handler: async (sub) => ({ groups: await getGroupSeats(sub) }),
  },
  {
    name: "list_my_grants",
    description: "List the caller's roles and capabilities across all their seats.",
    inputSchema: { type: "object", properties: {} },
    handler: async (sub) => await getRolesAndGrants(sub),
  },
  {
    name: "list_group_decisions",
    description:
      "List the recent decisions (proposals) for one of the caller's groups.",
    inputSchema: {
      type: "object",
      properties: {
        groupSlug: { type: "string", description: "Group slug or id" },
      },
      required: ["groupSlug"],
    },
    handler: async (sub, args) => {
      const slug = String(args?.groupSlug ?? "")
      return withIdentity(sub, async (client) => {
        // Explicit membership gate (mirrors decisions.ts) — don't rely on RLS alone.
        const member = await client.query(
          `SELECT 1 FROM group_members gm JOIN groups g ON g.id = gm.group_id
            WHERE (g.slug = $1 OR g.id::text = $1) AND gm.sub = $2`,
          [slug, sub],
        )
        if ((member.rowCount ?? 0) === 0) return { decisions: [] }
        const { rows } = await client.query(
          `SELECT p.id, p.title, p.status, p.quorum_pct, p.deadline, p.created_at
             FROM proposals p JOIN groups g ON g.id = p.group_id
            WHERE (g.slug = $1 OR g.id::text = $1)
            ORDER BY p.created_at DESC LIMIT 50`,
          [slug],
        )
        return { decisions: rows }
      })
    },
  },
]

// ---- upstream MCP servers (the aggregator/proxy part) ----
// MCP_UPSTREAMS = JSON: [{"name":"rag","url":"http://rag:8000/mcp"}, ...]
// The deep-agent-rag-stack exposes (or gets a thin MCP adapter to) an MCP
// endpoint; its tools are merged under "<name>.<tool>".

type Upstream = { name: string; url: string }

function parseUpstreams(raw?: string): Upstream[] {
  if (!raw) return []
  try {
    const v = JSON.parse(raw)
    return Array.isArray(v) ? v.filter((u) => u?.name && u?.url) : []
  } catch {
    return []
  }
}

const UPSTREAMS: Upstream[] = parseUpstreams(process.env.MCP_UPSTREAMS)

async function fetchUpstreamTools(u: Upstream, authHeader: string): Promise<McpTool[]> {
  const res = await fetch(u.url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      ...(authHeader ? { Authorization: authHeader } : {}),
    },
    body: JSON.stringify({ jsonrpc: "2.0", id: 1, method: "tools/list", params: {} }),
  })
  const data = (await res.json()) as any
  const tools = data?.result?.tools ?? []
  return tools.map((t: any) => ({
    name: `${u.name}.${t.name}`,
    description: t.description ?? "",
    inputSchema: t.inputSchema ?? { type: "object" },
    handler: async () => undefined, // never called — proxied
    upstream: u,
  }))
}

async function callUpstream(u: Upstream, toolName: string, args: any, authHeader: string): Promise<any> {
  const res = await fetch(u.url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      ...(authHeader ? { Authorization: authHeader } : {}),
    },
    body: JSON.stringify({
      jsonrpc: "2.0",
      id: 2,
      method: "tools/call",
      params: { name: toolName, arguments: args ?? {} },
    }),
  })
  return res.json()
}

// ---- JSON-RPC dispatch ----

async function listTools(sub: string, grants: string[], authHeader: string): Promise<McpTool[]> {
  const local = LOCAL_TOOLS.filter((t) => !t.grant || grants.includes(t.grant))
  const proxied: McpTool[] = []
  for (const u of UPSTREAMS) {
    try {
      proxied.push(...(await fetchUpstreamTools(u, authHeader)))
    } catch {
      // upstream down — skip it rather than fail the whole list
    }
  }
  return [...local, ...proxied]
}

function toolToSchema(t: McpTool) {
  return { name: t.name, description: t.description, inputSchema: t.inputSchema }
}

function textContent(data: unknown) {
  return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] }
}

export default async function mcpRoutes(fastify: FastifyInstance) {
  fastify.post("/mcp", async (request, reply) => {
    const claims = verifyBearer(request, reply)
    if (!claims) return // 401 already sent

    const sub = String((claims as any).sub ?? "")
    const authHeader = String(request.headers.authorization ?? "")
    const body = (request.body ?? {}) as any
    const id = body.id
    const method = String(body.method ?? "")

    // Resolve grants once per request (for tool filtering + gate checks).
    let grants: string[] = []
    try {
      grants = (await getRolesAndGrants(sub)).grants
    } catch {
      // grant lookup failed (DB down) — fall back to empty; RLS still guards data
    }

    // JSON-RPC notifications carry no id — ack and move on.
    if (id === undefined || id === null) {
      return reply.code(202).send()
    }

    const respond = (result: unknown) => reply.send({ jsonrpc: "2.0", id, result })
    const error = (code: number, message: string) =>
      reply.send({ jsonrpc: "2.0", id, error: { code, message } })

    try {
      switch (method) {
        case "initialize":
          return respond({
            protocolVersion: "2025-03-26",
            capabilities: { tools: {} },
            serverInfo: { name: "coop-api-mcp", version: "1.0.0" },
          })
        case "ping":
          return respond({})
        case "tools/list": {
          const tools = await listTools(sub, grants, authHeader)
          return respond({ tools: tools.map(toolToSchema) })
        }
        case "tools/call": {
          const name = String(body.params?.name ?? "")
          const args = body.params?.arguments ?? {}

          // Proxied upstream tool?
          const upstream = UPSTREAMS.find((u) => name.startsWith(`${u.name}.`))
          if (upstream) {
            const localName = name.slice(upstream.name.length + 1)
            const res = await callUpstream(upstream, localName, args, authHeader)
            if (res?.error) return error(-32000, `upstream error: ${res.error.message}`)
            return respond(res?.result ?? {})
          }

          const tool = LOCAL_TOOLS.find((t) => t.name === name)
          if (!tool) return error(-32602, `unknown tool: ${name}`)
          if (tool.grant && !grants.includes(tool.grant)) {
            return error(-32002, `missing grant: ${tool.grant}`)
          }
          const data = await tool.handler(sub, args)
          return respond(textContent(data))
        }
        default:
          return error(-32601, `method not found: ${method}`)
      }
    } catch (err) {
      fastify.log.error({ err: (err as Error).message }, "mcp tool call failed")
      return error(-32603, `internal error: ${(err as Error).message}`)
    }
  })
}
