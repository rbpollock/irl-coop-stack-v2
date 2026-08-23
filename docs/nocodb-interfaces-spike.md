# NocoDB Interfaces — Implementation Spike

Recovered from `nocodb/nocodb@develop` (sparse: `packages/nc-gui`, `packages/nocodb-sdk`,
`packages/nocodb/src/controllers/internal`, `.../meta/migrations/v0`) and cross-checked
against the deployed `irlcoop/nocodb-gate-sso:2026.08.8` bundle + live `nocodb` DB.

## 1. Verdict

**Implementing the Interfaces view is feasible — and better-specified than expected.**
The public (AGPL) repo ships the complete **type model**, **data model**, and the
frontend **data-adapter contract**; only the *implementation* (backend handlers +
builder frontend) is gated in the private `nocodb-ee` repo. That means this is a
**write-against-a-public-contract** job, not reverse-engineering.

The honest caveat: the backend handlers alone are NOT sufficient. The interface
**page shell + builder editor are EE frontend** and must also be written. That
frontend is the dominant cost.

## 2. What Interfaces is

A no-code app-builder over bases. 7 page layouts (`InterfacePageLayoutTypes`):
`TABLE`, `RECORD_REVIEW`, `DASHBOARD`, `FORM`, `OVERVIEW` (no source table),
`RECORD_DETAIL`, `CUSTOM`. Each page has a draft `config` + a `published_config`
snapshot (draft = builder-only; everyone else is forced onto published). Pages can
be shared publicly (read-only, page-level `uuid` + `password`) — TABLE/DASHBOARD only.

## 3. CE vs EE split (the key finding)

| Layer | CE (public, present) | EE (private, MISSING) |
|---|---|---|
| Types | `nocodb-sdk/src/lib/interface/*` — `pageConfigs.ts` (630 ln), `elements.ts`, `vizFields.ts`, `enums.ts`, `copyFromView.ts`, `index.ts` | — |
| Data model | migration `nc_202607251200_interfaces.ts` (creates `nc_interfaces` + `nc_interface_pages`, adds `PRINCIPAL_ASSIGNMENTS.hierarchy_scope`) — **applied in live DB** | — |
| Backend | internal-API dispatch framework + operation-name registry + `InternalApiModule` pattern + `OPERATION_SCOPES` + `batch` envelope | **~50 operation HANDLERS** (`InterfaceGet.operations.ts` / `InterfacePost.operations.ts` modules) |
| Frontend contract | `nc-gui/lib/interfaceData.ts` — full `InterfacePageDataApi` + `InterfaceRecordSidebarApi` + `InterfacePublicPageState` | adapter impl `ee/composables/useInterfacePageData.ts` |
| Frontend UI | create menu item, share/manage UI (`ShareInterface.vue`, `InterfaceMembers.vue`), permissions composable, shared smartsheet components (grid/kanban/gallery/…), localization | **the builder editor, page shell/nav, public-share consumer page** |

## 4. Data model (already in your DB)

```
nc_interfaces(id, fk_workspace_id, base_id, title, description, meta, order, hidden,
  first_published_at, last_published_at, created_by, owned_by, deleted, timestamps)
  PK (base_id, id)
nc_interface_pages(id, fk_workspace_id, base_id, fk_interface_id, fk_model_id, title,
  layout, meta, show_in_nav, visual_variant, config, published_config, is_published,
  keep_as_draft, draft_modified_at, published_at, error, uuid, password, order,
  created_by, deleted, timestamps)  PK (base_id, id)
PRINCIPAL_ASSIGNMENTS.hierarchy_scope   -- team-grant descendant expansion
```

`config`/`published_config` are JSON discriminated by `layout`. Defaults:
TABLE `{visualizations:[]}` · RECORD_REVIEW `{list:{item:{}},detail:{groups:[]}}` ·
DASHBOARD `{groups:[]}` · FORM `{groups:[]}` · OVERVIEW `{blocks:[],sidebar_blocks:[]}` ·
RECORD_DETAIL `{groups:[]}` · CUSTOM `{sources:[]}`.

Viz configs (grid/gallery/kanban/list/calendar/timeline/gantt) extend `InterfaceVizCommon`
(filters, sorts, `visible_field_ids`, `field_order`, `field_configs`, `color_by`,
`click_into_details`, `fk_detail_page_id`) + type-specific fields (`group_by`,
`stacking_field_id`, `date_ranges`, `row_height`, `frozen_column_count`, …).

## 5. Dispatch + integration point (exact template)

Ops reach handlers via the internal API — `/api/v2/internal/{workspaceId}/{baseId}`
with `?operation=<name>` (GET or POST), plus a `batch` envelope (≤25 read-only sub-ops,
`INTERNAL_BATCH_MAX_SIZE`). A handler module looks exactly like:

```ts
@Injectable()
export class InterfaceGetOperations implements InternalApiModule<InternalGETResponseType> {
  operations = ['interfaceList', 'interfaceGet', 'interfacePageList', /* … */] as const
  httpMethod = 'GET' as const
  publicBaseBlockedOperations = [/* sensitive reads */] as const
  async handle(context: NcContext, { req, payload }) { /* service call */ }
}
```

To port, mirror the existing pattern in three places:
1. `controllers/internal/modules/InterfaceGet.operations.ts` + `InterfacePost.operations.ts`
2. register in `provider.ts` `InternalApiModules[]`
3. add each op name to `operationScopes.ts` `OPERATION_SCOPES` (base scope; interface
   reads that must resolve on the unauthenticated share route are handled separately)

`internalBatch.ts` already names the EE files (`InterfaceGet.operations.ts`) and lists
the batchable interface reads.

## 6. Operation inventory

Shapes for meta ops come from SDK types (`InterfaceType`, `InterfacePageType`);
shapes for data ops come from the CE `InterfacePageDataApi` contract (method → op).

### Meta CRUD — 🟢 Easy (plain CRUD, tables + types public)
| Op | Method | Shape source |
|---|---|---|
| interfaceCreate / Update / Delete / Duplicate | POST | `InterfaceType` |
| interfaceList / interfaceGet / interfacePages / interfacePage | GET | `InterfaceType[]` / `InterfaceType` |
| interfacePageCreate / Update / Delete / Duplicate / ClearDraft | POST | `InterfacePageType` |
| interfacePageList / interfacePageGet / interfacePageIds | GET | `InterfacePageType[]` |

### Data fetch — 🟡 Medium (delegate to table-data services, compose scope)
| Op | Contract method (CE `interfaceData.ts`) |
|---|---|
| interfaceTableDataList | `fetchList({limit,offset,where,nestedWhere,filtersArr,sortsArr,…}) → {list,pageInfo}` |
| interfaceTableDataCount | `fetchCount` → `{count}` |
| interfaceTableGroupedDataList | `fetchGroupedData` → `[{key,value:{list,pageInfo}}]` |
| interfaceTableGroupBy | `fetchGroupBy` → `{list,pageInfo}` |
| interfaceTableCalendarDataList / ActiveDates | `fetchCalendarData` / `fetchCalendarActiveDates` |
| interfaceTableTimelineDataList | `fetchTimelineData` |
| interfaceTableGanttDataList / (+deps) | `fetchGanttData` / `fetchGanttDeps` → `{edges}` |
| interfaceTableDataExport | `exportCsv` → `{id}` (job) |
| interfaceWidgetDataGet | dashboard widget data |
| interfaceTableLeveledDataList / Count (inferred) | `fetchLeveledList` / `fetchLeveledCount` |
| interfaceDataAggregate / interfaceBulkAggregate (inferred) | `fetchAggregate` / `fetchBulkAggregate` |

### Data write — 🟡 Medium (delegate to record services, write-path identity)
| Op | Contract method |
|---|---|
| interfaceRecordInsert / Update / Delete | `insertRow` / `updateRow` / `deleteRow` |
| interfaceRecordBulkUpdate / BulkDelete | `bulkUpdateRows` / `bulkDeleteRows` |
| interfaceRecordGet (inferred) | `fetchRecord(rowId)` |
| interfaceRecordDuplicate (inferred) | `duplicateRow` |
| interfaceButtonHook (inferred) | `triggerButtonHook` |

### Links (LTAR) — 🟡 Medium (delegate to LTAR link services)
`interfaceRecordLinkAdd/Remove/Swap/SwapBulk/ByDisplay` ← `nestedLink/unlink/copyPaste/bulkCopyPaste/bulkLinkByDisplay`; also `nestedList`/`nestedExcludedList` (read).

### Grants — 🟠 Medium-Hard (new ACL resolution)
`interfaceGrantSet` / `interfaceGrantDelete` / `interfaceGrantScope` — resolve
`interface_role` + per-page `page_roles` + `hierarchy_scope` (team expansion) → effective
role with base-role fallback. Writes into `PRINCIPAL_ASSIGNMENTS`.

### Comments / audit — 🟡 Medium (delegate to comment/audit services, interface-scoped)
`interfaceCommentList/Row/Update/Delete/Resolve/Count` + `interfaceRecordAuditList`
(inferred) ← `InterfaceRecordSidebarApi`.

### Publishing / misc — 🟢 Easy
`interfacePageClearDraft`; `interfacePreviewWriteBlocked` (read-only gate);
`interfaceLayoutSupportsCopyFromView`, `interfaceTableSuffix` (config hints);
`interfaceNotFound` / `interfacePageNotFound` (error strings).

## 7. Frontend reality — the dominant cost

Backend 404→200 is necessary but NOT sufficient. After `interfaceCreate` succeeds the
frontend navigates into an interface page whose **shell + builder are EE**. Rebuilding
them means: page shell/nav, per-layout renderers, the builder canvas (add/configure
widgets, field curation, filters, publish), grant/share management, and the public
consumer page. The smartsheet components (grid/kanban/gallery) are reusable from CE,
and the data adapter is a single well-specified composable — but the builder itself is
effectively a mini no-code editor.

## 8. Options

- **A. Full reimplementation** (backend + builder + page shell + public share):
  **~1–3 months**, weighted toward the builder.
- **B. Backend + data adapter + minimal read-only shell** — get interfaces working
  programmatically (create via API, render TABLE/FORM pages with existing components),
  defer the builder: **~2 weeks** for a usable first cut.
- **C. Scoped** — implement only the layouts + ops a specific coop use case needs
  (e.g. TABLE + FORM), skip DASHBOARD/CUSTOM/calendar/gantt: **~1 week**.

## 9. Recommended first milestone (proof-of-concept)

Port the **meta-CRUD handlers** only (`interfaceCreate/List/Get/Update/Delete` +
`interfacePageCreate/List/Get`) into the fork using the `InternalApiModule` pattern,
deploy, and flip the journey's `interfaceCreate` SKIP → assert **200**. This is the
lowest-risk slice, directly resolves the 404, and validates the build/deploy/verify
loop before touching the data layer or frontend.
