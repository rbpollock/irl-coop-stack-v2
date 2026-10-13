# App admission — audit against the bar

Status: note · 2026-10-04 · Robbie + Hermes.
A **dated snapshot**, not a design. The rule is `where-facts-live.md` §4.1; the procedural checklist is
`irl-coop-apps` → `references/app-admission-bar.md`.

**Method, and its limits.** This audit is **derived from the app specs, the design docs and `REALITY.md`
— it is not a live verification.** No container was probed. Cells are marked:

- **✓** — documented as working, with a named artifact or a verified E2E in the docs
- **~** — partial, planned, or designed-but-unwired
- **?** — no evidence found either way (a real check would settle it)

## The table

| App | mapping | gate | event leg | marker | reconciler | Score |
|---|---|---|---|---|---|---|
| **Stalwart** (mail) | ✓ domain binding | ✓ OIDC directory | ~ | **✓ DNS TXT** | **✓✓ enumerates DNS** | **4** |
| **ERPNext** | ✓ `Company` ↔ group | ✓ Social Login Key | ~ notifications designed | **✓** the Company is *named after the group* | ✓ `provisionOnSignIn` | **4** |
| **LiteFarm** | ✓✓ `farm_id` ↔ `groups.id` | ✓ `litefarm-gate` | ✓ bus source | ✓ `farm.group_id`/`farm_name` | ✓ sync-on-login | **4–5** |
| **Matrix** | ~ room→group "later" (`db.ts` events comment) | ✓ native OIDC | **✓✓ appservice → bus** | ~ | ? | **~3** |
| **NocoDB** | ✓ one base per group | ✓ `_irlnocodb` gate-sso | ? | ~ base name | ✓ `enforce-nocodb-visibility.sh` | **~3** |
| **Plane** | ✓ project ↔ group | ✓ native OIDC, E2E verified | ~ `project.completed` designed | ~ | ? | **~2.5** |
| **Formbricks** | ✓ group mapping documented | ✓ `_irlformbricks` | ~ | ? | ? | **~2.5** |
| **MinIO** | ✓ per-group prefix | ✓ `_irlminio` | ? | ~ | ? | **~2** |
| **Hi.Events** | ? | ✓ public/gated split | ✓ webhooks | ? | ? | **~2** |
| **Webstudio** | ~ embed templates | spec exists (`enabled: false`) | ? | ? | ? | **~1** (not wired) |

## What the table shows

1. **The best-integrated apps are the ones the coop already treats as a projection** — Stalwart, ERPNext,
   LiteFarm (each 4+). **The weakest are the ones adopted as standalone tools** — Hi.Events, Formbricks,
   Webstudio, MinIO (~1–2.5). Adoption without integration is what R-10 measures.
2. **No app clears all four.** The gap is concentrated in the **two back half** requirements — *marker*
   and *reconciler* — which is exactly what `declared-binding-registry.md` §3 lists as a **"Now"** item
   ("adopt a marker convention per app and build the reconciler"). It is designed and not verifiably
   built. That is the single highest-leverage gap in this table: **two of four requirements are missing
   almost everywhere, and they are the two that make bindings rebuildable.**
3. **Mail is the reference implementation** — Stalwart's binding is discoverable because the marker lives
   in **DNS**, and the reconciler **enumerates DNS, not Stalwart**. That is the pattern to copy.
4. **ERPNext's marker is free by construction**: its tenant is a `Company` named after the group
   verbatim. Nothing had to be added — which is why it sits at the top, and why it is the natural centre
   for the `central-resource-store.md` direction.
5. **`REALITY.md` already names the honest gap** this table measures differently: *"Cross-app role
   mapping is bespoke per app; nothing shows a member's effective access in one place."* The bar is the
   same complaint from the integration side.

## What a real check would add (the verification pass, not done here)

- **Matrix**: is `resource_scopes` populated for rooms today, or still "later"?
- **NocoDB / Plane / Formbricks**: does anything emit to `events`, or are their event legs aspirational?
- **Every app**: does a marker convention exist in the app's own fields right now?
- **`enforce-nocodb-visibility.sh`** is the one reconciler that may already exist outside mail/ERPNext —
  confirm its scope.
- **Webstudio**: `enabled: false` — the table's score is about its *spec*, not a running app.

## The provisional vetted set

On this evidence: **Stalwart, ERPNext, LiteFarm** clear the bar's intent (with markers/reconcilers to
finish), **Matrix** is close and carries the bus, and everything else runs but **cannot yet be
authoritative**. Nothing moves into or out of the set without all four, and a sector profile may only
name a default app from whatever the set is.

## Cross-references

- `where-facts-live.md` §4.1 — the rule and the bar.
- `crm-under-fact-kinds.md` — the bar applied to a pending decision (D-22).
- `declared-binding-registry.md` §3 — the marker/reconciler work this table shows is outstanding.
- `REALITY.md` — per-capability honest status, the source for several cells.
- `RISKS.md` R-10 — the divergence this audit quantifies.