-- plane_user_view.sql — per-user scoped view over Plane's Postgres (plane-db)
-- irl.coop structure-aware: NocoDB (or any DB consumer) connects its external
-- source to Plane's postgres and reads ONE view per user, scoped by the realm
-- subject (users.sub). No mirror, no copy — the view is a WHERE clause on the
-- data itself.
--
-- Usage: substitute %SUB% with the Keycloak realm subject, then run against
-- plane-db. Sub names contain hyphens, so the view name is sanitized
-- (non-alphanumerics -> '_'). The view is granted to the consumer role.
--
-- Semantics: projects the user can actually see — public projects in any
-- workspace they belong to, plus private projects they are a member of.

CREATE OR REPLACE VIEW plane_projects__%SUB_SANITIZED% AS
SELECT DISTINCT
    p.id          AS project_id,
    p.name        AS project_name,
    p.identifier  AS project_identifier,
    p.network     AS visibility,          -- 0 = private (group), 2 = public
    p.group_id    AS group_id,            -- irl.coop group link
    p.safe_address AS safe_address,       -- group Safe once it exists
    w.slug        AS workspace_slug,
    p.created_at
FROM projects p
JOIN workspaces w     ON w.id = p.workspace_id AND w.deleted_at IS NULL
JOIN users u          ON u.sub = '%SUB%'
LEFT JOIN workspace_members wm
       ON wm.workspace_id = w.id AND wm.member_id = u.id AND wm.is_active
LEFT JOIN project_members pm
       ON pm.project_id = p.id AND pm.member_id = u.id AND pm.is_active
WHERE p.deleted_at IS NULL
  AND (p.network = 2 OR pm.id IS NOT NULL);

-- Example: GRANT SELECT ON plane_projects__<sub> TO nocodb;
