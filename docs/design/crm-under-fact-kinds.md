# The CRM question under the fact-kind split — ERPNext-native vs Twenty

Status: design · 2026-10-04 · Robbie + Hermes.
Revisits the parked Twenty intent in light of `where-facts-live.md`.
Resolves **D-22** (which CRM: ERPNext-native or Twenty) to a recommendation.
Companions: `app-admission-audit.md` (the bar, measured) · `erpnext-tenancy-notifications.md` (Company =
tenant) · `mautic-calcom-mcp-inference.md` + `local-ai-chat.md` (where Twenty/Payload were parked) ·
`adversary-models-and-sector-fit.md` (a relationship graph is a targeting tool).

## 0. What the parked intent asked for — and what the rule says it cannot be

Twenty was parked as the **member/relationship layer** alongside Payload as the content layer
(`local-ai-chat.md`). Under the fact-kind split, that framing is the problem:

| Fact | Kind | Owner |
|---|---|---|
| who is a member, and of which group | **1 — identity & membership** | **ours** |
| who may see a relationship record | **3 — disclosure** | **ours** |
| who committed to what (a partnership, a sponsorship) | **2 — authority & commitment** | **ours** (`declared_binding`) |
| contacts, activity, pipeline, notes, deals | **5 — operational records** | **the app's** |
| invoices, orders | 5 / **6 money** | ERPNext; money truth stays the ledger |

**So a CRM can only ever be a kind-5 app.** It may hold operational records *about* relationships. It
may not own membership, and it may never be the thing that decides who sees what.

This is not a technicality — it is the whole answer to "should this be Twenty or ERPNext", because
`REALITY.md` states the CRM's own success criterion as:

> *"A contact/relationship record scoped to, and visible only within, one group."*

That is a **disclosure property**. It is kind 3. So the milestone cannot be met *inside* any CRM — it is
met by the coop projecting the record through the dial. A CRM's own permission model is never the answer,
whichever CRM it is.

## 1. The decision, on the bar

`app-admission-audit.md` measured both candidates:

| | mapping | gate | event leg | marker | reconciler | Score |
|---|---|---|---|---|---|---|
| **ERPNext (live)** | ✓ `Company` ↔ group | ✓ Social Login Key | ~ designed | **✓ free** — the Company is named after the group | ✓ `provisionOnSignIn` | **4** |
| **Twenty (not deployed)** | ✗ | ✗ | ✗ | ✗ | ✗ | **0** |

**Recommendation: ERPNext-native, and keep Twenty parked with a stated trigger.** Twenty needs all five
built (~a full admission) *and* then becomes a second CRM's worth of drift. ERPNext is already at four of
five, already mapped, already reconciled on login — and by construction already carries a marker
nobody had to write.

**Honest about the counter-argument.** ERPNext's CRM is a *transactional* CRM — Lead, Opportunity,
Customer, Contract — a sales shape. The coop's relationship layer is a **mutual-aid / partnership
graph**, which is a different shape and may genuinely need a different tool. That is not a reason to
adopt Twenty now; it is the **trigger**:

> **Revisit when a real group needs a relationship UX that ERPNext's CRM cannot express** — not before.
> If it happens, Twenty enters as a **kind-5 app only**, behind the gate, projected through our
> disclosure layer, with a marker and a reconciler — never as a second identity store.

## 2. What this changes about the original intent

- **Twenty as the "member/relationship layer" — withdrawn.** Identity is kind 1 and stays ours; a second
  membership store is exactly R-10. What remains available is Twenty as a **CRM UI over kind-5 records**.
- **Payload (CMS) — same shape.** Content is kind 5; the *published* page is our projection (kind 3).
  So Payload's role is "a tool a group writes content in", never "the source of what the world sees".
- **A relationship graph is adversary-sensitive.** `adversary-models-and-sector-fit.md` treats an org
  chart as a targeting tool, so relationship data is high-value: it belongs behind the dial, at the
  coarsest granularity that serves the use case — and never in a store whose own permission model we do
  not control.

## 3. Decisions

| # | Decision | Recommendation |
|---|---|---|
| 1 | D-22: which CRM? | **ERPNext-native.** Twenty parked, trigger = a relationship UX ERPNext cannot express |
| 2 | Does Twenty ever hold identity? | **No.** Kind 5 only; membership stays in coop-api |
| 3 | What must exist before *any* CRM is authoritative for a relationship record? | The bar (§0) **plus** the disclosure projection — `REALITY.md`'s own milestone |

## Cross-references

- `where-facts-live.md` — the split; §4.1 the bar.
- `app-admission-audit.md` — the same bar measured across ten apps.
- `erpnext-tenancy-notifications.md` — the tenancy this recommendation relies on.
- `declared-binding-registry.md` §R5 — `authority_class`, for a partnership that *commits* something.
- `mautic-calcom-mcp-inference.md`, `local-ai-chat.md` — the parked intent this narrows.
- `REALITY.md` (CRM row) — the milestone that is a disclosure property, not a CRM feature.
- D-22 in `docs/DECISIONS.md` — open; this doc is the recommendation to close it.