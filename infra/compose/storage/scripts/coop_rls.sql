-- Coop row-level security on the group projection (Citus `irlcoop`).
-- Identity = `app.sub` (a per-request session variable set by coop-api).
-- Row visibility is enforced by Postgres, not the app — no app-level bypass.
--
-- RBAC seam: extend `coop_can_view_group` with role checks (owner/editor/
-- viewer) later without touching the tables or the app.
--
-- Why FORCE RLS + a BYPASSRLS helper role: coop-api connects as the table
-- OWNER (coop), so without FORCE the policies would never fire for it. The
-- membership helpers are SECURITY DEFINER owned by `coop_rls` (BYPASSRLS) so
-- they can read members/groups without recursing through the very policies
-- they implement.
--
-- Spike scope: SELECT is row-restricted (the read-permission proof); writes are
-- permissive so group creation still works. Write-side RBAC is the follow-up.

DO $rls$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'coop_rls') THEN
    CREATE ROLE coop_rls NOLOGIN;
  END IF;
END
$rls$;
ALTER ROLE coop_rls BYPASSRLS;
GRANT SELECT ON groups, group_members, resource_scopes TO coop_rls;

CREATE OR REPLACE FUNCTION coop_current_sub() RETURNS text AS $$
  SELECT NULLIF(current_setting('app.sub', true), '')::text
$$ LANGUAGE sql STABLE;

CREATE OR REPLACE FUNCTION coop_is_member(gid uuid) RETURNS boolean
SECURITY DEFINER SET search_path = public AS $$
  SELECT EXISTS (
    SELECT 1 FROM group_members gm WHERE gm.group_id = gid AND gm.sub = coop_current_sub()
  )
$$ LANGUAGE sql STABLE;
ALTER FUNCTION coop_is_member(uuid) OWNER TO coop_rls;

CREATE OR REPLACE FUNCTION coop_can_view_group(gid uuid) RETURNS boolean
SECURITY DEFINER SET search_path = public AS $$
  SELECT EXISTS (
    SELECT 1 FROM groups g
    WHERE g.id = gid AND (g.privacy = 'open' OR coop_is_member(g.id))
  )
$$ LANGUAGE sql STABLE;
ALTER FUNCTION coop_can_view_group(uuid) OWNER TO coop_rls;

-- groups
ALTER TABLE groups FORCE ROW LEVEL SECURITY;
ALTER TABLE groups ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS groups_select ON groups;
CREATE POLICY groups_select ON groups FOR SELECT USING (privacy = 'open' OR coop_is_member(id));
DROP POLICY IF EXISTS groups_write ON groups;
CREATE POLICY groups_write ON groups FOR INSERT WITH CHECK (true);
DROP POLICY IF EXISTS groups_update ON groups;
CREATE POLICY groups_update ON groups FOR UPDATE USING (true);
DROP POLICY IF EXISTS groups_delete ON groups;
CREATE POLICY groups_delete ON groups FOR DELETE USING (true);

-- group_members
ALTER TABLE group_members FORCE ROW LEVEL SECURITY;
ALTER TABLE group_members ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS group_members_select ON group_members;
CREATE POLICY group_members_select ON group_members FOR SELECT USING (coop_can_view_group(group_id));
DROP POLICY IF EXISTS group_members_write ON group_members;
CREATE POLICY group_members_write ON group_members FOR INSERT WITH CHECK (true);
DROP POLICY IF EXISTS group_members_update ON group_members;
CREATE POLICY group_members_update ON group_members FOR UPDATE USING (true);
DROP POLICY IF EXISTS group_members_delete ON group_members;
CREATE POLICY group_members_delete ON group_members FOR DELETE USING (true);

-- resource_scopes
ALTER TABLE resource_scopes FORCE ROW LEVEL SECURITY;
ALTER TABLE resource_scopes ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS resource_scopes_select ON resource_scopes;
CREATE POLICY resource_scopes_select ON resource_scopes FOR SELECT USING (coop_can_view_group(group_id));
DROP POLICY IF EXISTS resource_scopes_write ON resource_scopes;
CREATE POLICY resource_scopes_write ON resource_scopes FOR INSERT WITH CHECK (true);
DROP POLICY IF EXISTS resource_scopes_update ON resource_scopes;
CREATE POLICY resource_scopes_update ON resource_scopes FOR UPDATE USING (true);
DROP POLICY IF EXISTS resource_scopes_delete ON resource_scopes;
CREATE POLICY resource_scopes_delete ON resource_scopes FOR DELETE USING (true);
