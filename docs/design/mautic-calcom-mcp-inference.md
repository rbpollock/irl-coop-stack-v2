# Stack additions — Mautic, Cal.com, MCP knowledgebase, client-side inference

Status: design · Sep 2026 · Builds on android-mini-services-client.md (the phone
as a node), smtp-relay.md (coop-api → Stalwart SMTP), and the "weave" notion of a
RAG-fueled, scoped AI inference engine.

Four additions, noted as intent:

## 1. Mautic — marketing automation

Open-source marketing automation (email campaigns, segments, journeys) for the
coop's own communications and, scoped, for group-level email. Same heavyweight
pattern as NocoDB/Formbricks: a PHP app + DB behind an oauth2-proxy OIDC gate,
SMTP outbound through the coop-api relay → Stalwart. Group-scoped via
`resource_scopes` like every other app.

## 2. Cal.com — scheduling & booking

Open-source scheduling (group events, meetings, and — potentially — paid
bookings). The paid-booking path is where this touches the economic model: it is
one of the fee levers the coop could take a percentage on (see the "fee on
bookings" idea), with percentages decided by members.

## 3. MCP server + knowledgebase

A Model Context Protocol server that exposes coop tools and data as MCP tools,
backed by a knowledgebase (the design docs, the world-doc projection, and stack
state — RAG-indexed). This is the shared, scoped "AI gateway": the caller's coop
JWT maps to the same seats/grants projection as any other app, so an AI can only
see and do what the member it acts for can.

**Built (first slice):** `apps/coop-api/src/mcp.ts` — a JSON-RPC-over-POST
`/mcp` endpoint on coop-api (streamable-HTTP shape, tools-only, no SSE). The
caller's coop JWT scopes tool listing by grant, and each local tool runs inside
`withIdentity(sub)` so Postgres RLS scopes the data. Three read tools live now
(`list_my_groups`, `list_my_grants`, `list_group_decisions`); upstream MCP
servers aggregate via `MCP_UPSTREAMS` (merged as `<name>.<tool>`, forwarded on
call). Write tools, the RAG stack's MCP endpoint, and the on-device client are
the next slices.

## 4. Client-side inference calling the MCP tools

Inference runs **on the member's device** (a quantized local model), not on a
big-tech API — the same sovereignty thread as the phone-as-node. The local model
(RAG, scoped to the knowledgebase) invokes the MCP server for anything that needs
the stack: reading group state, drafting a proposal, acting on governance.

## How it composes

- **Mautic / Cal.com** → communication and workflow pillars, OIDC-gated, SMTP via
  the relay, scoped by seats.
- **MCP server** → a new surface; the caller is an OIDC client, its tools are
  grant-gated (the same `roles → grants` matrix as the apps).
- **Client-side inference** → the edge does the thinking, the MCP gateway does
  the acting, nothing leaves the member's device except the scoped tool calls.

## Open questions

- Mautic: which fork/version, and does it need the same Gate-SSO auto-login
  treatment as NocoDB/Formbricks?
- ~~Cal.com: which fork/version?~~ — **ANSWERED 2026-09-13: use `cal.diy`, not
  Cal.com.** Cal.com's main repository went closed-source; `cal.diy` is the
  community-driven fork with **all enterprise/commercial code removed and a
  100% MIT licence**. For a project whose core claims are "open source reduces
  costs" and "no proprietary dependency", upstream Cal.com is now the wrong
  side of that line. It is also the *self-hostable community edition*, which is
  the deployment shape this doc assumes.
- Cal.com paid bookings: does the group treasury need a booking→ledger
  integration before this is useful? — **and note the BYO decision
  (`money-in-and-out.md` §5.2): a paid-booking path must land in a GROUP
  TREASURY, never a member's personal payment account.**
- **Is Twenty CRM redundant?** `local-ai-chat.md` parks a CRM (Twenty) and a CMS
  (Payload) as the "member/relationship layer". **ERPNext already ships a CRM** —
  Lead, Opportunity, Sales Pipeline, Appointments, Quotation → Customer → Sales
  Order (docs.frappe.io/erpnext/CRM) — and ERPNext is already live at
  `accounting.irl.coop`. Note the shape difference before deciding: ERPNext's CRM
  is *sales-pipeline* shaped, while "member/relationship layer" may want something
  broader. Resolve by asking what the relationship layer must actually do, not by
  which app is nicer.
- MCP auth: read-only vs. write tools (governance, treasury) — and how to keep a
  write path provable and revocable.
- Client-side inference: which quantized models actually run on a phone, and the
  honest battery/compute budget.

## Why

The same through-line as the phone-as-node: inference and action move to the edge,
the coop's MCP gateway is the one shared, scoped, privacy-first interface, and
Mautic/Cal.com round out the communication and workflow pillars.
