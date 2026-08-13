-- Coop row-level security on the group projection (Citus `irlcoop`).
-- Identity = `app.sub` (a per-request session variable set by coop-api).
-- Enforcement lives in Postgres, not the app — no app-level bypass.
--
-- RBAC model: a group row records its `created_by`; ownership is a
-- group_members seat with role 'owner'. Read permission = open OR member;
-- write permission = owner (groups + members) / member (scopes). Fine-grained
-- roles later extend these helpers (coop_is_owner / coop_is_member /
-- coop_can_view_group) — no table or app change needed.
--
-- Why FORCE RLS + a BYPASSRLS helper role: coop-api connects as the table
-- OWNER (coop), so without FORCE the policies would never fire for it. The
-- helpers are SECURITY DEFINER owned by `coop_rls` (BYPASSRLS) so they can read
-- members/groups without recursing through the very policies they implement.

DO $rls$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'coop_rls') THEN
    CREATE ROLE coop_rls NOLOGIN;
  END IF;
END
$rls$;
ALTER ROLE coop_rls BYPASSRLS;
GRANT SELECT ON groups, group_members, resource_scopes TO coop_rls;

-- ownership column (one-time backfill from the existing owner seat)
ALTER TABLE groups ADD COLUMN IF NOT EXISTS created_by text;
UPDATE groups g SET created_by = (
  SELECT gm.sub FROM group_members gm
  WHERE gm.group_id = g.id AND 'owner' = ANY(gm.roles) LIMIT 1
) WHERE g.created_by IS NULL;

-- identity
CREATE OR REPLACE FUNCTION coop_current_sub() RETURNS text AS $$
  SELECT NULLIF(current_setting('app.sub', true), '')::text
$$ LANGUAGE sql STABLE;

-- membership (any seat)
CREATE OR REPLACE FUNCTION coop_is_member(gid uuid) RETURNS boolean
SECURITY DEFINER SET search_path = public AS $$
  SELECT EXISTS (
    SELECT 1 FROM group_members gm WHERE gm.group_id = gid AND gm.sub = coop_current_sub()
  )
$$ LANGUAGE sql STABLE;
ALTER FUNCTION coop_is_member(uuid) OWNER TO coop_rls;

-- ownership (seat with role 'owner')
CREATE OR REPLACE FUNCTION coop_is_owner(gid uuid) RETURNS boolean
SECURITY DEFINER SET search_path = public AS $$
  SELECT EXISTS (
    SELECT 1 FROM group_members gm
    WHERE gm.group_id = gid AND gm.sub = coop_current_sub() AND 'owner' = ANY(gm.roles)
  )
$$ LANGUAGE sql STABLE;
ALTER FUNCTION coop_is_owner(uuid) OWNER TO coop_rls;

-- creator (the group row's created_by) — bootstraps the first owner seat
CREATE OR REPLACE FUNCTION coop_is_creator(gid uuid) RETURNS boolean
SECURITY DEFINER SET search_path = public AS $$
  SELECT EXISTS (
    SELECT 1 FROM groups g WHERE g.id = gid AND g.created_by = coop_current_sub()
  )
$$ LANGUAGE sql STABLE;
ALTER FUNCTION coop_is_creator(uuid) OWNER TO coop_rls;

-- read permission (privacy tier + membership + creator)
CREATE OR REPLACE FUNCTION coop_can_view_group(gid uuid) RETURNS boolean
SECURITY DEFINER SET search_path = public AS $$
  SELECT EXISTS (
    SELECT 1 FROM groups g
    WHERE g.id = gid
      AND (g.privacy = 'open' OR coop_is_member(g.id) OR g.created_by = coop_current_sub())
  )
$$ LANGUAGE sql STABLE;
ALTER FUNCTION coop_can_view_group(uuid) OWNER TO coop_rls;

-- groups
ALTER TABLE groups FORCE ROW LEVEL SECURITY;
ALTER TABLE groups ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS groups_select ON groups;
-- creator is always visible to themselves (created_by) so INSERT ... RETURNING
-- works before the owner seat row exists; without it the new group is invisible
-- under the SELECT policy and the RETURNING clause raises a spurious RLS error.
CREATE POLICY groups_select ON groups FOR SELECT USING (
  privacy = 'open' OR coop_is_member(id) OR created_by = coop_current_sub()
);
DROP POLICY IF EXISTS groups_insert ON groups;
DROP POLICY IF EXISTS groups_write ON groups;
CREATE POLICY groups_insert ON groups FOR INSERT WITH CHECK (created_by = coop_current_sub());
DROP POLICY IF EXISTS groups_update ON groups;
CREATE POLICY groups_update ON groups FOR UPDATE USING (coop_is_owner(id));
DROP POLICY IF EXISTS groups_delete ON groups;
CREATE POLICY groups_delete ON groups FOR DELETE USING (coop_is_owner(id));

-- group_members
ALTER TABLE group_members FORCE ROW LEVEL SECURITY;
ALTER TABLE group_members ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS group_members_select ON group_members;
CREATE POLICY group_members_select ON group_members FOR SELECT USING (coop_can_view_group(group_id));
DROP POLICY IF EXISTS group_members_insert ON group_members;
DROP POLICY IF EXISTS group_members_write ON group_members;
CREATE POLICY group_members_insert ON group_members FOR INSERT WITH CHECK (
  coop_is_owner(group_id)
  OR (sub = coop_current_sub() AND 'owner' = ANY(roles) AND coop_is_creator(group_id))
);
DROP POLICY IF EXISTS group_members_update ON group_members;
CREATE POLICY group_members_update ON group_members FOR UPDATE USING (coop_is_owner(group_id));
DROP POLICY IF EXISTS group_members_delete ON group_members;
CREATE POLICY group_members_delete ON group_members FOR DELETE USING (coop_is_owner(group_id));

-- resource_scopes
ALTER TABLE resource_scopes FORCE ROW LEVEL SECURITY;
ALTER TABLE resource_scopes ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS resource_scopes_select ON resource_scopes;
CREATE POLICY resource_scopes_select ON resource_scopes FOR SELECT USING (coop_can_view_group(group_id));
DROP POLICY IF EXISTS resource_scopes_insert ON resource_scopes;
DROP POLICY IF EXISTS resource_scopes_write ON resource_scopes;
CREATE POLICY resource_scopes_insert ON resource_scopes FOR INSERT WITH CHECK (coop_is_member(group_id));
DROP POLICY IF EXISTS resource_scopes_update ON resource_scopes;
CREATE POLICY resource_scopes_update ON resource_scopes FOR UPDATE USING (coop_is_member(group_id));
DROP POLICY IF EXISTS resource_scopes_delete ON resource_scopes;
CREATE POLICY resource_scopes_delete ON resource_scopes FOR DELETE USING (coop_is_member(group_id));
