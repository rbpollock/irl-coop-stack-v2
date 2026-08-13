# Design Spec: World-Doc Virtual Workspace & NocoDB Integration

Status: draft (vision record & schema spec). Author: Robbie + Hermes, Aug 2026.

## The Model

The **World-Doc Virtual Workspace** is a per-user, read-only aggregated schema inside PostgreSQL (Citus), projected natively into **NocoDB** as a single, unified virtual spreadsheet view. 

Instead of fanning out queries to a dozen different microservice databases, NocoDB connects to a single PostgreSQL endpoint on the Citus coordinator and reads a unified view scoped deterministically by the user's realm subject (`sub`).

```
 +--------------------------------------------------------------------------+
 |                      WORLD-DOC VIRTUAL WORKSPACE                         |
 +--------------------------------------------------------------------------+
 |  Item Type  |   Item ID   |    Title / Name    |  Group  |  App Context  |
 +-------------+-------------+--------------------+---------+---------------+
 |  project    |  proj_0x12  | Cold Storage Coop  | 0xabc...| plane-db      |
 |  group      |  grp_0x456  | Farm Coalition     | 0xdef...| irlcoop-db    |
 |  contacts   |  usr_0x789  | Alice (Coordinator)| 0xabc...| roundcube-db  |
 |  treasury   |  tx_0x99a   | Entitled Grant #4  | 0xdef...| safe-onchain  |
 +--------------------------------------------------------------------------+
```

## 1. Unified SQL View Schema

Every authenticated user gets a CREATE2-style deterministic view name sanitized for PostgreSQL (`world_doc__%SUB_SANITIZED%`), mapped in the database like so:

```sql
CREATE OR REPLACE VIEW world_doc__%SUB_SANITIZED% AS

-- 1. Plane Projects (from plane-db view projection)
SELECT 
    'project'       AS item_type,
    project_id      AS item_id,
    project_name    AS item_title,
    safe_address    AS group_address,
    'plane-db'      AS app_context,
    workspace_slug  AS details_metadata,
    created_at      AS updated_at
FROM plane_projects__%SUB_SANITIZED%

UNION ALL

-- 2. Sovereign Groups (from irlcoop-db)
SELECT 
    'group'         AS item_type,
    g.id            AS item_id,
    g.name          AS item_title,
    g.safe_address  AS group_address,
    'irlcoop-db'    AS app_context,
    g.description   AS details_metadata,
    g.updated_at
FROM groups g
JOIN group_members gm ON gm.group_id = g.id AND gm.user_sub = '%SUB%'

UNION ALL

-- 3. Group-Aware Contacts (from directory projection)
SELECT 
    'contact'       AS item_type,
    c.sub           AS item_id,
    c.display_name  AS item_title,
    g.safe_address  AS group_address,
    'roundcube-db'  AS app_context,
    c.email         AS details_metadata,
    c.updated_at
FROM directory_contacts c
JOIN group_members gm ON gm.user_sub = c.sub
JOIN groups g        ON g.id = gm.group_id
WHERE gm.user_sub = '%SUB%';
```

## 2. NocoDB Projection Integration

NocoDB consumes this via its patched **Gate-SSO auto-login** module:
1. When a user logs in, NocoDB resolves their `sub` identity from the `X-Forwarded-Email` header.
2. NocoDB mounts the corresponding `world_doc__%SUB_SANITIZED%` view inside the user's dashboard view.
3. The user sees a single, unified spreadsheet list containing all their projects, tools, contacts, and treasury transactions across every group and app they participate in.
