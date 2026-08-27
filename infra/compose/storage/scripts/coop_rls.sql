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
GRANT SELECT, INSERT, UPDATE, DELETE ON groups, group_members, resource_scopes, events, notification_reads, notification_digests, profiles TO coop_rls;

-- ownership column (one-time backfill from the existing owner seat)
ALTER TABLE groups ADD COLUMN IF NOT EXISTS created_by text;
UPDATE groups g SET created_by = (
  SELECT gm.sub FROM group_members gm
  WHERE gm.group_id = g.id AND 'owner' = ANY(gm.roles) LIMIT 1
) WHERE g.created_by IS NULL;

-- personal groups ("the user is their own group") — kind marker + nullable Safe
ALTER TABLE groups ADD COLUMN IF NOT EXISTS kind text NOT NULL DEFAULT 'coop';
ALTER TABLE groups ALTER COLUMN safe_address DROP NOT NULL;

-- Canonical group slug ({slug}.irl.coop → group). Nullable (personal groups
-- have no public subdomain); unique among named groups. The availability check
-- must be privacy-blind — a members/hidden group's slug is still un-takeable —
-- so it is a SECURITY DEFINER (BYPASSRLS as coop_rls) function, not an RLS read.
ALTER TABLE groups ADD COLUMN IF NOT EXISTS slug text;
CREATE UNIQUE INDEX IF NOT EXISTS groups_slug_uniq ON groups (slug) WHERE slug IS NOT NULL;

CREATE OR REPLACE FUNCTION coop_slug_taken(p_slug text) RETURNS boolean
SECURITY DEFINER SET search_path = public AS $$
  SELECT EXISTS (SELECT 1 FROM groups WHERE slug = p_slug)
$$ LANGUAGE sql STABLE;
ALTER FUNCTION coop_slug_taken(text) OWNER TO coop_rls;


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

-- "the user is their own group": idempotently provision a personal group for the
-- current sub (no Safe yet — the personal account Safe is deployed separately,
-- deterministic sub-derived salt). SECURITY DEFINER + BYPASSRLS so it can write
-- the row regardless of the write RLS policies.
CREATE OR REPLACE FUNCTION coop_ensure_personal_group() RETURNS uuid
SECURITY DEFINER SET search_path = public AS $$
DECLARE
  sub text := coop_current_sub();
  gid uuid;
BEGIN
  IF sub IS NULL THEN RETURN NULL; END IF;
  SELECT id INTO gid FROM groups WHERE kind = 'personal' AND created_by = sub LIMIT 1;
  IF gid IS NULL THEN
    INSERT INTO groups (safe_address, name, privacy, kind, created_by)
    VALUES (NULL, 'Personal', 'members', 'personal', sub)
    RETURNING id INTO gid;
    INSERT INTO group_members (group_id, sub, roles, visibility)
    VALUES (gid, sub, ARRAY['owner'], 'canonical');
  END IF;
  RETURN gid;
END;
$$ LANGUAGE plpgsql;
ALTER FUNCTION coop_ensure_personal_group() OWNER TO coop_rls;

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

-- events
-- SELECT is RLS-scoped (a member sees their groups' events). There is no
-- user INSERT policy: ingestion is a *system* write (source -> gateway ->
-- store) via the SECURITY DEFINER coop_ingest_event below, which bypasses
-- RLS as coop_rls — the appservice never authenticates as a user.
ALTER TABLE events FORCE ROW LEVEL SECURITY;
ALTER TABLE events ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS events_select ON events;
CREATE POLICY events_select ON events FOR SELECT USING (coop_can_view_group(group_id));

-- Ingest one event for a sender `sub` (system write): resolves/creates the
-- sender's personal group ("the user is their own group"), then inserts the
-- event under that group. Idempotent on (source, source_event_id).
CREATE OR REPLACE FUNCTION coop_ingest_event(
  p_sub text, p_source text, p_source_event_id text,
  p_type text, p_payload jsonb, p_occurred_at timestamptz
) RETURNS uuid
SECURITY DEFINER SET search_path = public AS $$
DECLARE
  gid uuid;
  eid uuid;
BEGIN
  IF p_sub IS NULL THEN RETURN NULL; END IF;
  SELECT id INTO gid FROM groups WHERE kind = 'personal' AND created_by = p_sub LIMIT 1;
  IF gid IS NULL THEN
    INSERT INTO groups (safe_address, name, privacy, kind, created_by)
    VALUES (NULL, 'Personal', 'members', 'personal', p_sub)
    RETURNING id INTO gid;
    INSERT INTO group_members (group_id, sub, roles, visibility)
    VALUES (gid, p_sub, ARRAY['owner'], 'canonical');
  END IF;

  INSERT INTO events (group_id, source, source_event_id, type, payload, occurred_at)
  VALUES (gid, p_source, p_source_event_id, p_type, p_payload, p_occurred_at)
  ON CONFLICT DO NOTHING
  RETURNING id INTO eid;
  RETURN eid;
END;
$$ LANGUAGE plpgsql;
ALTER FUNCTION coop_ingest_event(text,text,text,text,jsonb,timestamptz) OWNER TO coop_rls;

-- Delivery outbox (option A): the Temporal deliverySweep claims undelivered
-- events and stamps delivered_at once a delivery channel accepts them. System-
-- level (SECURITY DEFINER, BYPASSRLS as coop_rls) — the sweep is a system
-- consumer, not a user, so it must see ALL undelivered events, not a caller's
-- groups. The coop role calls these via the shared pool; they execute as
-- coop_rls and bypass RLS.
CREATE OR REPLACE FUNCTION coop_sweep_undelivered(p_limit int DEFAULT 100)
RETURNS SETOF uuid
SECURITY DEFINER SET search_path = public AS $$
  SELECT id FROM events WHERE delivered_at IS NULL ORDER BY occurred_at LIMIT p_limit
$$ LANGUAGE sql STABLE;
ALTER FUNCTION coop_sweep_undelivered(int) OWNER TO coop_rls;

CREATE OR REPLACE FUNCTION coop_mark_event_delivered(p_id uuid) RETURNS void
SECURITY DEFINER SET search_path = public AS $$
  UPDATE events SET delivered_at = now() WHERE id = p_id
$$ LANGUAGE sql;
ALTER FUNCTION coop_mark_event_delivered(uuid) OWNER TO coop_rls;

-- Read-state (user-scoped, not group-scoped). A user may read/clear only their
-- own rows — enforced here in Postgres, not the app. FORCE RLS so the coop
-- table-owner role is also scoped by it.
ALTER TABLE notification_reads FORCE ROW LEVEL SECURITY;
ALTER TABLE notification_reads ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS notification_reads_all ON notification_reads;
CREATE POLICY notification_reads_all ON notification_reads
  USING (user_sub = coop_current_sub())
  WITH CHECK (user_sub = coop_current_sub());

ALTER TABLE notification_digests FORCE ROW LEVEL SECURITY;
ALTER TABLE notification_digests ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS notification_digests_all ON notification_digests;
CREATE POLICY notification_digests_all ON notification_digests
  USING (user_sub = coop_current_sub())
  WITH CHECK (user_sub = coop_current_sub());

-- Digest candidate collector (system-level, BYPASSRLS as coop_rls): for every
-- group member, the events in their groups that are (a) older than the digest
-- window, (b) unanswered (no read/clear row), and (c) not already digested.
-- Sender-scoped today (each event's group is the sender's personal group), so
-- gm.sub == the sender; once room→group mapping (resource_scopes) lands this
-- same query fans out to every real member automatically.
CREATE OR REPLACE FUNCTION coop_collect_digest_candidates(p_older_than interval)
RETURNS TABLE(user_sub text, event_id uuid, source text, type text, payload jsonb, occurred_at timestamptz, group_id uuid)
SECURITY DEFINER SET search_path = public AS $$
  SELECT gm.sub, e.id, e.source, e.type, e.payload, e.occurred_at, e.group_id
  FROM events e
  JOIN group_members gm ON gm.group_id = e.group_id
  WHERE e.occurred_at < now() - p_older_than
    AND NOT EXISTS (
      SELECT 1 FROM notification_reads nr
      WHERE nr.event_id = e.id AND nr.user_sub = gm.sub
        AND (nr.read_at IS NOT NULL OR nr.cleared_at IS NOT NULL)
    )
    AND NOT EXISTS (
      SELECT 1 FROM notification_digests nd
      WHERE nd.event_id = e.id AND nd.user_sub = gm.sub
    )
  ORDER BY gm.sub, e.source, e.occurred_at
$$ LANGUAGE sql STABLE;
ALTER FUNCTION coop_collect_digest_candidates(interval) OWNER TO coop_rls;

-- Mark a (user, event) pair as folded into a digest (system-level write).
CREATE OR REPLACE FUNCTION coop_mark_digested(p_sub text, p_id uuid) RETURNS void
SECURITY DEFINER SET search_path = public AS $$
  INSERT INTO notification_digests (user_sub, event_id) VALUES (p_sub, p_id)
  ON CONFLICT DO NOTHING
$$ LANGUAGE sql;
ALTER FUNCTION coop_mark_digested(text, uuid) OWNER TO coop_rls;

-- Postiz sync (system-level, BYPASSRLS as coop_rls): projects groups into
-- Postiz's Organization/UserOrganization tables. Opt-in = a resource_scopes row
-- with app='postiz'; the group's UUID IS the Postiz Organization id (deterministic
-- link — no placeholder→org transition), so the resource_scopes row is stable.
CREATE OR REPLACE FUNCTION coop_postiz_opted_groups()
RETURNS TABLE(group_id uuid, name text)
SECURITY DEFINER SET search_path = public AS $$
  SELECT g.id, g.name
  FROM groups g
  WHERE EXISTS (
    SELECT 1 FROM resource_scopes rs WHERE rs.group_id = g.id AND rs.app = 'postiz'
  )
  ORDER BY g.created_at
$$ LANGUAGE sql STABLE;
ALTER FUNCTION coop_postiz_opted_groups() OWNER TO coop_rls;

-- Seats for one group, with the coop profile email (may be NULL — the sync
-- falls back to the Keycloak admin lookup for the canonical address).
CREATE OR REPLACE FUNCTION coop_postiz_seats(p_group uuid)
RETURNS TABLE(sub text, roles text[], email text)
SECURITY DEFINER SET search_path = public AS $$
  SELECT gm.sub, gm.roles, p.email
  FROM group_members gm
  LEFT JOIN profiles p ON p.sub = gm.sub
  WHERE gm.group_id = p_group
$$ LANGUAGE sql STABLE;
ALTER FUNCTION coop_postiz_seats(uuid) OWNER TO coop_rls;

-- User profile (display name / avatar / onboarded) — user-scoped like read-state:
-- a user may read/write only their own row, enforced here in Postgres.
ALTER TABLE profiles FORCE ROW LEVEL SECURITY;
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS profiles_all ON profiles;
CREATE POLICY profiles_all ON profiles
  USING (sub = coop_current_sub())
  WITH CHECK (sub = coop_current_sub());

-- ---------------------------------------------------------------------------
-- Roles-as-bundles-of-grants + telephony (added with the FreeSWITCH pillar).
-- ---------------------------------------------------------------------------

-- Capability check: does the current sub hold a role (in group_members.roles)
-- that grants `g` for group `gid`? SECURITY DEFINER (BYPASSRLS as coop_rls) so
-- it can read group_members without recursing through the policies that call it.
CREATE OR REPLACE FUNCTION coop_has_grant(gid uuid, g text) RETURNS boolean
SECURITY DEFINER SET search_path = public AS $$
  SELECT EXISTS (
    SELECT 1
    FROM group_members gm
    JOIN roles r ON r.name = ANY(gm.roles)
    JOIN role_grants rg ON rg.role_id = r.id
    WHERE gm.group_id = gid
      AND gm.sub = coop_current_sub()
      AND rg.grant_name = g
  )
$$ LANGUAGE sql STABLE;
ALTER FUNCTION coop_has_grant(uuid, text) OWNER TO coop_rls;

-- Platform admin (FusionPBX ops gate). `platform-admin` is a PLATFORM-scoped
-- role (grants telephony.platform.admin) that lives on the member's personal
-- 1-of-1 seat. Unlike owner/telephony-admin it is NOT bundled by any builtin
-- role, so promoting is an explicit operator act. SECURITY DEFINER (BYPASSRLS
-- as coop_rls) and idempotent: promotion is additive (never strips existing
-- roles), revocation removes only platform-admin.

-- coop_ops: least-privilege operator role that may promote/demote. LOGIN, holds
-- ONLY EXECUTE on the two functions below (no table grants, not superuser). Its
-- password is the derived secret ${SECRET:coop.ops} (env COOP_OPS), set at
-- bootstrap via `ALTER ROLE coop_ops PASSWORD ...` (coop_rls.sql has no secrets
-- access). The app role `coop` is deliberately locked OUT below.
DO $ops$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'coop_ops') THEN
    CREATE ROLE coop_ops LOGIN;
  END IF;
END
$ops$;

CREATE OR REPLACE FUNCTION coop_ensure_platform_admin(sub_arg text) RETURNS void
SECURITY DEFINER SET search_path = public AS $$
DECLARE
  gid uuid;
BEGIN
  IF sub_arg IS NULL THEN RETURN; END IF;
  IF session_user NOT IN ('postgres', 'coop_ops') THEN
    RAISE EXCEPTION 'coop_ensure_platform_admin: operator-only (session_user=%)', session_user;
  END IF;
  SELECT id INTO gid FROM groups WHERE kind = 'personal' AND created_by = sub_arg LIMIT 1;
  IF gid IS NULL THEN
    INSERT INTO groups (safe_address, name, privacy, kind, created_by)
    VALUES (NULL, 'Personal', 'members', 'personal', sub_arg)
    RETURNING id INTO gid;
    INSERT INTO group_members (group_id, sub, roles, visibility)
    VALUES (gid, sub_arg, ARRAY['owner','platform-admin'], 'canonical');
  ELSE
    UPDATE group_members
       SET roles = ARRAY(SELECT DISTINCT x FROM unnest(roles || ARRAY['owner','platform-admin']) AS x)
     WHERE group_id = gid AND sub = sub_arg;
  END IF;
  -- Audit: record EVERY promotion (source_event_id NULL => never deduped).
  PERFORM coop_ingest_event(sub_arg, 'platform', NULL, 'platform_admin.granted',
                            jsonb_build_object('sub', sub_arg, 'actor', session_user), now());
END;
$$ LANGUAGE plpgsql;
ALTER FUNCTION coop_ensure_platform_admin(text) OWNER TO coop_rls;

CREATE OR REPLACE FUNCTION coop_revoke_platform_admin(sub_arg text) RETURNS void
SECURITY DEFINER SET search_path = public AS $$
DECLARE
  gid uuid;
BEGIN
  IF sub_arg IS NULL THEN RETURN; END IF;
  IF session_user NOT IN ('postgres', 'coop_ops') THEN
    RAISE EXCEPTION 'coop_revoke_platform_admin: operator-only (session_user=%)', session_user;
  END IF;
  SELECT id INTO gid FROM groups WHERE kind = 'personal' AND created_by = sub_arg LIMIT 1;
  IF gid IS NOT NULL THEN
    UPDATE group_members
       SET roles = ARRAY(SELECT x FROM unnest(roles) AS x WHERE x <> 'platform-admin')
     WHERE group_id = gid AND sub = sub_arg;
  END IF;
  PERFORM coop_ingest_event(sub_arg, 'platform', NULL, 'platform_admin.revoked',
                            jsonb_build_object('sub', sub_arg, 'actor', session_user), now());
END;
$$ LANGUAGE plpgsql;
ALTER FUNCTION coop_revoke_platform_admin(text) OWNER TO coop_rls;

-- Lock the promotion path to coop_ops (superuser postgres always bypasses).
-- `coop` (the app role) and any member code path get neither EXECUTE nor a pass
-- through the session_user guard — no self-promotion, even from a future bug.
REVOKE EXECUTE ON FUNCTION coop_ensure_platform_admin(text) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION coop_revoke_platform_admin(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION coop_ensure_platform_admin(text) TO coop_ops;
GRANT EXECUTE ON FUNCTION coop_revoke_platform_admin(text) TO coop_ops;

-- group_telephony: owner/telephony-admin administered, member-readable.
ALTER TABLE group_telephony FORCE ROW LEVEL SECURITY;
ALTER TABLE group_telephony ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS group_telephony_select ON group_telephony;
CREATE POLICY group_telephony_select ON group_telephony FOR SELECT USING (coop_can_view_group(group_id));
DROP POLICY IF EXISTS group_telephony_insert ON group_telephony;
CREATE POLICY group_telephony_insert ON group_telephony FOR INSERT WITH CHECK (coop_has_grant(group_id, 'telephony.admin'));
DROP POLICY IF EXISTS group_telephony_update ON group_telephony;
CREATE POLICY group_telephony_update ON group_telephony FOR UPDATE USING (coop_has_grant(group_id, 'telephony.admin'));
DROP POLICY IF EXISTS group_telephony_delete ON group_telephony;
CREATE POLICY group_telephony_delete ON group_telephony FOR DELETE USING (coop_has_grant(group_id, 'telephony.admin'));

-- telephony_resources: system-provisioned (no user write policy), member-readable.
ALTER TABLE telephony_resources FORCE ROW LEVEL SECURITY;
ALTER TABLE telephony_resources ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS telephony_resources_select ON telephony_resources;
CREATE POLICY telephony_resources_select ON telephony_resources FOR SELECT USING (coop_can_view_group(group_id));

-- Catalog tables (grants/roles/role_grants/telephony_templates) have no RLS:
-- any authenticated member reads; operator writes are gated at the app layer.

-- Grant table access to coop_rls (BYPASSRLS helper role) for the new tables.
GRANT SELECT, INSERT, UPDATE, DELETE ON group_telephony, telephony_resources, telephony_templates, grants, roles, role_grants TO coop_rls;

-- System-write bridge for telephony resources (the provisioning path's
-- projection write). SECURITY DEFINER + owned by coop_rls (BYPASSRLS) so it can
-- write telephony_resources despite the no-user-write RLS policy, and locked to
-- coop_ops so the app's `coop` pool can never mint a resource on its own. Also
-- stamps the resource_scopes row that makes CDR/call events group-resolvable
-- through the existing ingest fan-out. Idempotent.
CREATE OR REPLACE FUNCTION coop_provision_telephony_resource(
  p_group_id            uuid,
  p_group_telephony_id  uuid,
  p_resource_type       text,
  p_external_ref        text,
  p_config              jsonb DEFAULT '{}'::jsonb
) RETURNS uuid
SECURITY DEFINER SET search_path = public AS $$
DECLARE
  rid uuid;
BEGIN
  IF session_user NOT IN ('postgres', 'coop_ops') THEN
    RAISE EXCEPTION 'coop_provision_telephony_resource: operator-only (session_user=%)', session_user;
  END IF;
  INSERT INTO telephony_resources (group_id, group_telephony_id, resource_type, external_ref, config)
  VALUES (p_group_id, p_group_telephony_id, p_resource_type, p_external_ref, p_config)
  ON CONFLICT (group_id, resource_type, external_ref) DO NOTHING
  RETURNING id INTO rid;
  INSERT INTO resource_scopes (group_id, app, resource_key, scoped_by)
  VALUES (p_group_id, 'freeswitch', p_external_ref, 'system')
  ON CONFLICT (group_id, app, resource_key) DO NOTHING;
  RETURN rid;
END;
$$ LANGUAGE plpgsql;
ALTER FUNCTION coop_provision_telephony_resource(uuid, uuid, text, text, jsonb) OWNER TO coop_rls;
REVOKE EXECUTE ON FUNCTION coop_provision_telephony_resource(uuid, uuid, text, text, jsonb) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION coop_provision_telephony_resource(uuid, uuid, text, text, jsonb) TO coop_ops;
