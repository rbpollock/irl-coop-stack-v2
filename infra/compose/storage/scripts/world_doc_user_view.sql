-- world_doc_user_view.sql — per-user world-doc projection (Layer 2, Citus `irlcoop`).
-- One view per realm sub: everything the user can see across their groups,
-- already filtered by group privacy. Read by NocoDB / Plane via an external-source
-- connection to the Citus `irlcoop` database. No copy — a projection.
--
-- The groups / group_members / resource_scopes tables are self-provisioned by
-- coop-api at boot (apps/coop-api/src/db.ts). This view is the query surface
-- apps consume; materialize it per user with %SUB% + %SUB_SANITIZED% substituted
-- (sanitize: non-alphanumerics -> '_', same rule as plane_user_view.sql).

CREATE OR REPLACE VIEW world_doc__%SUB_SANITIZED% AS
-- my groups (with my seat)
SELECT
    'group'        AS item_type,
    g.id::text     AS item_id,
    g.name         AS item_title,
    g.safe_address AS group_address,
    g.privacy      AS privacy,
    gm.roles       AS roles,
    g.created_at   AS updated_at
FROM groups g
JOIN group_members gm ON gm.group_id = g.id
WHERE gm.sub = '%SUB%'

UNION ALL

-- resources scoped to my groups
SELECT
    'resource'                   AS item_type,
    rs.resource_key              AS item_id,
    rs.app || ':' || rs.resource_key AS item_title,
    g.safe_address               AS group_address,
    g.privacy                    AS privacy,
    NULL::text[]                 AS roles,
    rs.scoped_at                 AS updated_at
FROM resource_scopes rs
JOIN groups g         ON g.id = rs.group_id
JOIN group_members gm ON gm.group_id = g.id
WHERE gm.sub = '%SUB%';
