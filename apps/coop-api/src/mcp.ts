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
          `SELECT 1 FROM coop_my_seats() gm JOIN groups g ON g.id = gm.group_id
            WHERE (g.slug = $1 OR g.id::text = $1)`,
          [slug],
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
  {
    name: "memory.recall",
    description:
      "Recall the caller's own assistant memory — durable, explicit facts the assistant has remembered or the member has saved. Member-owned and erasable.",
    inputSchema: {
      type: "object",
      properties: {
        query: { type: "string", description: "Optional free-text filter" },
      },
    },
    handler: async (sub, args) => {
      const q = String(args?.query ?? "").trim()
      return withIdentity(sub, async (client) => {
        const { rows } = q
          ? await client.query(
              `SELECT id, fact, source, kind, created_at FROM member_memory
                WHERE sub = $1 AND fact ILIKE '%' || $2 || '%'
                ORDER BY created_at DESC LIMIT 200`,
              [sub, q],
            )
          : await client.query(
              `SELECT id, fact, source, kind, created_at FROM member_memory
                WHERE sub = $1 ORDER BY created_at DESC LIMIT 200`,
              [sub],
            )
        return { memories: rows }
      })
    },
  },
  {
    name: "memory.remember",
    description:
      "Write a durable fact to the caller's own memory. Explicit: the caller confirms each fact (nothing is written silently), and every fact is erasable.",
    inputSchema: {
      type: "object",
      properties: {
        fact: { type: "string", description: "The fact to remember" },
        kind: {
          type: "string",
          description: "Optional tag: fact / decision / group / preference",
        },
        source: {
          type: "string",
          enum: ["member", "assistant"],
          description: "Who authored it (member-saved vs harness-proposed-and-confirmed)",
        },
      },
      required: ["fact"],
    },
    handler: async (sub, args) => {
      const fact = String(args?.fact ?? "").trim()
      if (!fact) return { error: "fact is required" }
      const kind = String(args?.kind ?? "fact")
      const source = args?.source === "assistant" ? "assistant" : "member"
      return withIdentity(sub, async (client) => {
        const { rows } = await client.query(
          `INSERT INTO member_memory (sub, fact, source, kind) VALUES ($1, $2, $3, $4)
           RETURNING id, fact, source, kind, created_at`,
          [sub, fact, source, kind],
        )
        return { memory: rows[0] }
      })
    },
  },
  {
    name: "memory.forget",
    description: "Erase one fact from the caller's own memory by id.",
    inputSchema: {
      type: "object",
      properties: { id: { type: "string", description: "The memory id to erase" } },
      required: ["id"],
    },
    handler: async (sub, args) => {
      const id = String(args?.id ?? "").trim()
      if (!id) return { error: "id is required" }
      return withIdentity(sub, async (client) => {
        const res = await client.query(
          `DELETE FROM member_memory WHERE sub = $1 AND id = $2`,
          [sub, id],
        )
        return { erased: (res.rowCount ?? 0) > 0 }
      })
    },
  },
]

// ---- upstream MCP servers (the aggregator/proxy part) ----
// MCP_UPSTREAMS = JSON: [{"name":"rag","url":"http://rag:8000/mcp"}, ...]
// The deep-agent-rag-stack exposes (or gets a thin MCP adapter to) an MCP
// endpoint; its tools are merged under "<name>.<tool>".

// Upstream policy is DEFAULT-DENY. An upstream must opt in with `public: true`
// to be LISTED and CALLED by an anonymous caller; otherwise it requires an
// authenticated member and may additionally require a capability grant. This
// is what stops "add an app" from silently widening the tool surface: without
// an explicit declaration an upstream is invisible AND uncallable anonymously.
type Upstream = { name: string; url: string; public?: boolean; grant?: string }

function upstreamAllowed(u: Upstream, authed: boolean, grants: string[]): boolean {
  if (u.grant && !grants.includes(u.grant)) return false
  if (u.public === true) return true
  return authed
}

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
  // A non-2xx upstream (e.g. rag-api rejecting our token with 401) has no
  // `.result`, so returning res.json() here used to hand the caller an empty
  // `{}` that looked like a SUCCESSFUL empty answer — the widget then read "no
  // context" and the assistant said it had nothing in the coop's knowledge,
  // while the real cause (a failed login to the retrieval service) was invisible.
  // Surface it as a JSON-RPC error so it is loud, and so callers can fall back.
  if (!res.ok) {
    let detail = ""
    try {
      detail = JSON.stringify(await res.json())
    } catch {
      detail = await res.text().catch(() => "")
    }
    return {
      error: {
        code: -32000,
        message: `upstream ${u.name} HTTP ${res.status}${detail ? `: ${detail.slice(0, 200)}` : ""}`,
      },
    }
  }
  return res.json()
}

// ---- JSON-RPC dispatch ----

async function listTools(sub: string, grants: string[], authHeader: string): Promise<McpTool[]> {
  const authed = sub !== "anonymous"
  // Anonymous guests: no member-local tools at all.
  const local = authed ? LOCAL_TOOLS.filter((t) => !t.grant || grants.includes(t.grant)) : []
  const proxied: McpTool[] = []
  for (const u of UPSTREAMS) {
    // Default-deny: an upstream that hasn't declared `public` is not even shown
    // to an anonymous caller (and a grant-gated one is hidden without it).
    if (!upstreamAllowed(u, authed, grants)) continue
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
    const rawAuth = request.headers.authorization
    const authHeader = String(rawAuth ?? "")
    let sub = "anonymous"
    let grants: string[] = []
    if (rawAuth) {
      const claims = verifyBearer(request, reply)
      if (!claims) return // 401 already sent
      sub = String((claims as any).sub ?? "")
      // Resolve grants once per request (for tool filtering + gate checks).
      try {
        grants = (await getRolesAndGrants(sub)).grants
      } catch {
        // grant lookup failed (DB down) — fall back to empty; RLS still guards data
      }
    }
    const body = (request.body ?? {}) as any
    const id = body.id
    const method = String(body.method ?? "")

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
          const authed = sub !== "anonymous"

          // Proxied upstream tool? Enforce the SAME policy as listing — hiding a
          // tool from tools/list is not access control, so a caller who knows the
          // name must still be refused.
          const upstream = UPSTREAMS.find((u) => name.startsWith(`${u.name}.`))
          if (upstream) {
            if (!upstreamAllowed(upstream, authed, grants)) {
              return error(
                -32002,
                `missing grant: ${upstream.grant ?? "authenticated member"}`
              )
            }
            const localName = name.slice(upstream.name.length + 1)
            const res = await callUpstream(upstream, localName, args, authHeader)
            if (res?.error) return error(-32000, `upstream error: ${res.error.message}`)
            return respond(res?.result ?? {})
          }

          const tool = LOCAL_TOOLS.find((t) => t.name === name)
          if (!tool) return error(-32602, `unknown tool: ${name}`)
          // Member-local tools are never callable anonymously: tools/list hides
          // them, but this path used to run them with sub="anonymous" — which let
          // an unauthenticated caller write a member_memory row.
          if (!authed) return error(-32001, "authentication required")
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
