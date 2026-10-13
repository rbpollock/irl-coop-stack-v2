# BYO inference providers & group-scoped agents

Status: design (decisions recorded) · 2026-10-04 · Builds on provider-seams.md (the
provider seam pattern), delegation-and-session-keys.md (the ERC-7715 grant, the agent-key
shape, the JWT bridge, the delegation registry), local-ai-chat.md (the chat harness and
its on-device generation), group-scoping.md (group = Safe, seats, resource_scopes, privacy
tiers) and group-secret-vault.md (group-held secrets). Enforcement point: the coop-api MCP
gateway (`apps/coop-api/src/mcp.ts`).

## 0. What this answers

Two questions:

1. **How does a member plug in their own inference provider and keys?** And a group, and
   the coop as a whole?
2. **How does an agent acting *for a group* authenticate, scoped to that group?**

The short answers: BYO inference is a **provider seam** (provider-seams.md) with three
tiers of provider, and it is **not** the BYO that §5.2 ruled out. Agent authentication is
the **ERC-7715 agent-key shape** from delegation-and-session-keys.md, carried through the
same JWT bridge the Temporal lane uses, enforced at the one MCP choke point.

## 1. First, do not conflate two BYOs

`money-in-and-out.md` §5.2 **DECIDED: no BYO rails** — an individual holding the payment
account breaks governance-controlled finance. That decision is about **money and
governance authority**, and it stands.

**Inference is a different domain.** It is *compute*: which model answers a prompt, and
whose budget pays for it. It is not on the governance path, holds no funds, and grants no
authority over group resources. So:

> **BYO inference providers are admitted. The §5.2 no-BYO rule is scoped to money and
> never cited against inference.** Recording this explicitly so the two are not confused
> later.

The reason BYO is *safe* here is the same reason it was *unsafe* for rails: an inference
key confers a capability (spend my compute, answer my prompt), not custody of anything the
group governs.

## 2. BYO inference is a provider seam

The chat harness (local-ai-chat.md) becomes provider-agnostic. It knows only the abstract
descriptor — **"an inference provider, id P, at base URL U, auth = a secret handle"** —
exactly as the core knows the rail only as `RAIL_URL`/`RAIL_ID`/`RAIL_AUTH_TOKEN`
(provider-seams.md §1). The vendor noun (`openai`, `anthropic`, `ollama`, `local`) lives in
one opaque descriptor column, never in the harness.

### 2.1 Declared, validated capabilities

Per provider-seams.md §2.6, every provider declares its capabilities and the core
validates them before use, refusing a provider that fails a need. For inference:

| capability | values | why it is load-bearing |
|---|---|---|
| **`locality`** | `on-device` / `on-host` / `third-party` | drives the **data-locality policy** (§4): a group may forbid third-party providers for its turns, so group data never leaves the coop. The core refuses the *adapter*, not the model. |
| `streaming` | bool | the chat surface expects a stream; a provider that cannot stream is refused for it |
| `tools` | bool | an agent turn that needs MCP tool-calls will not be handed a provider that cannot do them |
| `context` | tokens | a turn whose assembled prompt overflows is refused, not silently truncated |
| `cost_class` | free / metered / capped | policy can pick among N live providers (provider-seams.md §3) |
| `transport` | `server-mediated` / `client-direct` | see §3 |

### 2.2 Two at once, policy selects (provider-seams.md §3)

Multiple providers may be live simultaneously; a **policy** selects which id serves a
turn. Cutover — or a member switching provider — is a config change, not a code change.
This is the same mechanism the payment rail already proved.

## 3. Three tiers of provider, and where each key lives

Provider resolution runs **member preference → group policy → coop fallback**. The three
tiers map exactly onto the **two-domain secret model** of delegation-and-session-keys.md §2:

| tier | whose provider | where the credential lives |
|---|---|---|
| **member** | their own OpenAI / Anthropic / Ollama key, or a local endpoint on their machine | a **USER secret** — the member's Safe-anchored Vault slice, unlocked only by that member's session key. Never coop-api's process env, never Temporal's reach. |
| **group** | a provider the group holds and mandates | a **GROUP secret** — group-secret-vault.md, held by the group Safe |
| **platform** | the coop-run CPU fallback (llama.cpp `llama-server`, the app sibling to `rag-inference`) | a **PLATFORM secret** — `${SECRET:llm.inference}` in coop-api env, like `rag.inference` |

This is the same three-way split as the **visibility tiers** (personal / group / coop) —
one mental model for "whose is this and who can see it."

### 3.1 Transport — server-mediated vs client-direct

- **Client-direct** — on-device (Chrome Prompt API, local-ai-chat.md) and endpoints on the
  member's own machine (local Ollama). Nothing leaves the device; no secret crosses the
  wire. The default where it is available.
- **Server-mediated** — a BYO *third-party* key. coop-api holds the secret handle and acts
  as the adapter; the browser never sees the key. This crosses the "generation never leaves
  the browser" line that local-ai-chat.md draws — and that is the honest trade: a member
  using *their own* third-party key is choosing to send the prompt to that vendor. The
  Vault is what keeps the key itself off the client. The descriptor's `transport` flag
  makes the crossing explicit rather than silent.

## 4. Group provider policy — DECIDED

A group's provider policy is set by **governance vote** (delegation-and-session-keys.md §7:
who may set policy is itself a governance decision), and **group templates ship sensible
defaults** so a new group is configured before anyone votes on anything.

**Default posture (DECIDED): third-party providers are allowed by default, and are
forbidden by default only for `hidden` groups.** A group may *explicitly* forbid them
either way — the capability exists for everyone — but the automatic restriction is scoped
to hidden groups, where membership is itself commitment-based (group-scoping.md §3) and
routing a turn to a third party would leak the very thing the tier exists to conceal.

| group privacy | third-party provider default |
|---|---|
| open / members | allowed |
| hidden | **forbidden by default** (group may re-open explicitly) |

The policy is enforced at the seam: the core validates `locality` against the group's
policy and refuses a third-party adapter for a turn it may not serve.

## 5. How an agent authenticates with group scope

Two principals. They must not be merged.

### 5.1 The member's own harness

Already solved. The coop JWT (`sub`) → MCP `verifyBearer` → `withIdentity(sub)` → RLS to
their seats, tools grant-filtered (mcp.ts). The "group scope" of a member's agent is their
**seat-union** — the same union the retrieval reads (knowledge-aggregation.md).

### 5.2 A group-scoped agent

An agent acting *as the group* holds authority from the **group Safe**, not from any member:

> **An ERC-7715 grant from the group Safe to the agent's key** (delegation-and-session-keys.md
> §4 agent-key shape). Governance decides → the Safe signs the grant → the agent holds it.
> Narrow scope, lower caps, bounded expiry, human-in-the-loop above a value threshold
> (§9.3). The Safe is the kill switch (§3.3). **Never a service identity** — §2's no-bypass
> invariant stands: every actor is a named delegate with a visible, revocable scope.

The grant reaches the MCP gateway through **§5's JWT bridge, reused verbatim**: the agent
signs a challenge → coop-api validates the signature *and* the on-chain grant → coop-api
mints a **short-lived JWT whose claims carry `act: group:<id>` plus the granted scope** →
MCP runs `withIdentity(groupPrincipal)` and filters tools by the granted capability set.
Temporal stays a dumb JWT verifier; coop-api is the only thing that touches the chain.

The `grant` field already on `LOCAL_TOOLS` (mcp.ts) is the hook — an agent's JWT carries
its granted capabilities, and `tools/list` + `tools/call` filter on them. No new machinery.

### 5.3 DECIDED: the group principal is standard

`withIdentity` accepts a **group principal** — `app.sub` set to the group, policies
resolving group resources, the group's privacy tier applied — as the standard model for
group agents. **Not** member impersonation: running the agent as the granting member would
leak that member's *other* seats into the agent's reach. The group principal is narrower
and honest — it can reach exactly the group's resources and nothing else.

### 5.4 Same rule as the union

**An agent never exceeds the group's own visibility.** A group agent sees the group's
resources plus the public tier — never any member's private memory, never another group's
data. For `hidden` groups, the agent's grant is proven, not enumerated (group-scoping.md §3).

## 6. Agents are visible, named delegates — DECIDED

Every agent is a **named entry in the delegation registry** (delegation-and-session-keys.md
§8) — e.g. "the care-circle's intake agent" — with its holder, scope, and expiry, visible to
the members who can see that group. Members can see *who acted*. There is no anonymous
agent and no invisible system identity. This is what keeps "no bypass" true as agents
multiply: each is a named delegate, revocable at the Safe.

## 7. What already exists vs. what is new

**Reuse (do not rebuild):**

- Provider seam pattern and its rules — provider-seams.md §2.
- The ERC-7715 grant, agent-key shape, JWT bridge, delegation registry —
  delegation-and-session-keys.md §4/§5/§8.
- The MCP gateway, `verifyBearer` → `sub`, `withIdentity`, tool `grant` filtering — mcp.ts.
- The three-tier secret domains — delegation-and-session-keys.md §2; group secrets —
  group-secret-vault.md.
- MinIO STS per-member session keys — local-ai-chat.md (the device-delegation path).

**New build:**

1. **The group principal in RLS** — extend `withIdentity` to accept `group:<id>` and make
   the policies resolve group resources under the group's privacy tier. This is the one
   real gap; everything else is assembly.
2. **The inference descriptor + policy** — the provider registry row (id, base URL, secret
   handle, capabilities) and the resolution order (member → group → platform).
3. **The agent-JWT claim** — `act: group:<id>` minted in the §5 bridge, consumed by MCP
   tool filtering.

## 8. Decisions recorded

| # | Decision | Date |
|---|---|---|
| 1 | Group principal is the **standard** identity for group agents (not member impersonation) | 2026-10-04 |
| 2 | Group provider policy is set by **governance vote**; group **templates** carry sensible defaults | 2026-10-04 |
| 3 | Third-party providers are **allowed by default, forbidden by default only for hidden groups**; any group may explicitly forbid them | 2026-10-04 |
| 4 | Agents are **visible, named delegates** in the delegation registry | 2026-10-04 |

## 9. Open questions

- **Descriptor shape** — one opaque `provider_payload` column per the migration test
  (provider-seams.md §2.2/§2.4), or a normalized provider table? The seam rule says the
  vendor detail lives in one column; confirm the registry can still list/validate
  capabilities without a schema migration to add a provider.
- **Member default provider storage UX** — a BYO key is a user secret in the Vault; how
  the member sets it (dashboard settings vs. the provisioning delegation manifest) is a
  surface decision, not an architecture one.
- **Cost visibility** — a metered BYO provider spends the member's budget; whether turns
  show a running cost estimate belongs with the workflow-economics work.
- **First cutover drill** — per provider-seams.md §4, a seam you have never swapped is not
  a seam. The inference seam should get a drill: stand up the coop CPU fallback and the
  member's own provider, route a turn through each, cut between them, record the elapsed
  time. Schedule it.