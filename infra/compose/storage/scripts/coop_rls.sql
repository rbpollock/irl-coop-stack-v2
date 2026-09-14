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

-- Emit a contribution event for a TARGET group (not the sender's personal group). `events`
-- has no user INSERT policy — ingestion is a system write — so the human path cannot insert one
-- directly, which is what a naive `INSERT INTO events` in recordContribution discovered. This is
-- the narrow sibling of coop_ingest_event: same shape, but the event belongs to the group the
-- WORK belongs to (so the group sees it and the Tier-2 lane shards by it), and it refuses a
-- caller who is not a member of that group.
CREATE OR REPLACE FUNCTION coop_emit_contribution(
  p_group_id uuid, p_source text, p_source_event_id text, p_payload jsonb
) RETURNS uuid
SECURITY DEFINER SET search_path = public AS $$
DECLARE eid uuid;
BEGIN
  IF NOT coop_is_member(p_group_id) THEN
    RAISE EXCEPTION 'coop_emit_contribution: not a member of the target group';
  END IF;
  INSERT INTO events (group_id, source, source_event_id, type, payload)
  VALUES (p_group_id, p_source, p_source_event_id, 'contribution.logged', p_payload)
  ON CONFLICT DO NOTHING
  RETURNING id INTO eid;
  -- a dedup hit returns NULL; hand back the existing row instead of nothing, so a retry is
  -- idempotent at this layer too and not only in the ledger
  IF eid IS NULL THEN
    SELECT id INTO eid FROM events
     WHERE source = p_source AND source_event_id = p_source_event_id LIMIT 1;
  END IF;
  RETURN eid;
END;
$$ LANGUAGE plpgsql;
ALTER FUNCTION coop_emit_contribution(uuid,text,text,jsonb) OWNER TO coop_rls;

-- Ingest one event for an explicit GROUP target (system write): the activity
-- belongs to a group (a group workspace's ticket sales), not to a person, so it
-- lands on the GROUP's stream and RLS shows it to every member. The target is a
-- `groups.slug` (or the id as text) resolved here, because `groups` is RLS-forced
-- and a system source is not a member. Same dedupe as the personal variant —
-- `source_event_id` MUST therefore be unique across groups for a given source
-- (compose it with the group ref). Returns the event id + the resolved group.
CREATE OR REPLACE FUNCTION coop_ingest_group_event(
  p_group_ref text, p_source text, p_source_event_id text,
  p_type text, p_payload jsonb, p_occurred_at timestamptz
) RETURNS TABLE (id uuid, group_id uuid)
SECURITY DEFINER SET search_path = public AS $$
DECLARE
  gid uuid;
  eid uuid;
BEGIN
  IF p_group_ref IS NULL THEN RETURN; END IF;

  SELECT g.id INTO gid FROM groups g
   WHERE (g.slug = p_group_ref OR g.id::text = p_group_ref) AND g.kind <> 'personal'
   LIMIT 1;
  IF gid IS NULL THEN RETURN; END IF;

  INSERT INTO events (group_id, source, source_event_id, type, payload, occurred_at)
  VALUES (gid, p_source, p_source_event_id, p_type, p_payload, p_occurred_at)
  ON CONFLICT DO NOTHING
  RETURNING events.id INTO eid;

  RETURN QUERY SELECT eid, gid;
END;
$$ LANGUAGE plpgsql;
ALTER FUNCTION coop_ingest_group_event(text,text,text,text,jsonb,timestamptz) OWNER TO coop_rls;

-- The members of a group (system-level read, BYPASSRLS as coop_rls): the live
-- lane needs to fan a group-targeted event out to every member, and targeting
-- resolves here — server-side — so it can never be spoofed by a client.
CREATE OR REPLACE FUNCTION coop_group_member_subs(p_group uuid)
RETURNS SETOF text
SECURITY DEFINER SET search_path = public AS $$
  SELECT gm.sub FROM group_members gm
   WHERE gm.group_id = p_group AND gm.sub IS NOT NULL
$$ LANGUAGE sql STABLE;
ALTER FUNCTION coop_group_member_subs(uuid) OWNER TO coop_rls;

-- Delivery outbox (option A): the Temporal deliverySweep claims undelivered
-- events and stamps delivered_at once a delivery channel accepts them. System-
-- level (SECURITY DEFINER, BYPASSRLS as coop_rls) — the sweep is a system
-- consumer, not a user, so it must see ALL undelivered events, not a caller's
-- groups. The coop role calls these via the shared pool; they execute as
-- coop_rls and bypass RLS.
CREATE OR REPLACE FUNCTION coop_sweep_undelivered(p_limit int DEFAULT 100)
RETURNS SETOF uuid
SECURITY DEFINER SET search_path = public AS $$
  -- EXCLUDES contribution.* — those are records to materialise, not notifications to
  -- deliver. Both lanes claim from the same `events` pool and both mark rows delivered, so
  -- without this partition the delivery lane wins the race and the ledger never sees the
  -- work. One pool, two disjoint consumers.
  SELECT id FROM events
   WHERE delivered_at IS NULL
     AND type NOT LIKE 'contribution.%'
   ORDER BY occurred_at LIMIT p_limit
$$ LANGUAGE sql STABLE;
ALTER FUNCTION coop_sweep_undelivered(int) OWNER TO coop_rls;

CREATE OR REPLACE FUNCTION coop_mark_event_delivered(p_id uuid) RETURNS void
SECURITY DEFINER SET search_path = public AS $$
  UPDATE events SET delivered_at = now() WHERE id = p_id
$$ LANGUAGE sql;
ALTER FUNCTION coop_mark_event_delivered(uuid) OWNER TO coop_rls;

-- ---------------------------------------------------------------------------
-- The Tier-2 lane (docs/design/tier2-entry-model.md §5.6). `contribution.*` events are
-- the durable interface by which work becomes a ledger entry: a machine source writes only
-- the event, and this lane is the consumer. appendTier2Entry stays the ONLY writer.
--
-- Claim returns ids AND group_id so the sweep can keep a group's appends in order; the
-- read is type-guarded so it cannot be used to fetch an arbitrary event.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION coop_sweep_contributions(p_limit int DEFAULT 100)
RETURNS TABLE(id uuid, group_id uuid)
SECURITY DEFINER SET search_path = public AS $$
  SELECT e.id, e.group_id
    FROM events e
   WHERE e.delivered_at IS NULL
     AND e.type LIKE 'contribution.%'
   ORDER BY e.occurred_at, e.id
   LIMIT p_limit
$$ LANGUAGE sql STABLE;
ALTER FUNCTION coop_sweep_contributions(int) OWNER TO coop_rls;

CREATE OR REPLACE FUNCTION coop_contribution_event(p_id uuid)
RETURNS TABLE(id uuid, group_id uuid, source text, source_event_id text, type text, payload jsonb)
SECURITY DEFINER SET search_path = public AS $$
  SELECT e.id, e.group_id, e.source, e.source_event_id, e.type, e.payload
    FROM events e
   WHERE e.id = p_id
     AND e.type LIKE 'contribution.%'
$$ LANGUAGE sql STABLE;
ALTER FUNCTION coop_contribution_event(uuid) OWNER TO coop_rls;

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

-- Member AI-assistant memory — user-scoped like read-state/profiles: a member
-- may read/write/delete only their own facts, enforced here in Postgres.
ALTER TABLE member_memory FORCE ROW LEVEL SECURITY;
ALTER TABLE member_memory ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS member_memory_all ON member_memory;
CREATE POLICY member_memory_all ON member_memory
  USING (sub = coop_current_sub())
  WITH CHECK (sub = coop_current_sub());
GRANT SELECT, INSERT, UPDATE, DELETE ON member_memory TO coop_rls;

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

-- MGCP phone directory: the MAC→extension map for ShoreTel/MGCP phones, served
-- to FreeSWITCH's mod_xml_curl directory gateway so a phone resolves its
-- extension from the coop DB (MAC in the resource's config jsonb) instead of
-- hand-edited directory XML. SECURITY DEFINER (BYPASSRLS as coop_rls) so the
-- gateway can read every member's extension regardless of RLS.
CREATE OR REPLACE FUNCTION coop_mgcp_directory() RETURNS TABLE(extension text, mac text)
SECURITY DEFINER SET search_path = public AS $$
  SELECT tr.external_ref, tr.config->>'mgcp_mac'
    FROM telephony_resources tr
   WHERE tr.resource_type = 'extension'
     AND tr.config->>'mgcp_mac' IS NOT NULL
$$ LANGUAGE sql STABLE;
ALTER FUNCTION coop_mgcp_directory() OWNER TO coop_rls;

-- ---------------------------------------------------------------------------
-- Geo (sovereign maps): tracks / markers / waypoints — group-scoped like
-- resource_scopes. SELECT = a member/owner/creator of the group (public and
-- federated content is served by the API's anonymous path — no app.sub — not
-- RLS). INSERT = any member. UPDATE/DELETE = the object's owner or a group
-- owner. waypoints denormalize group_id/owner_id so their policies match.
-- ---------------------------------------------------------------------------
GRANT SELECT, INSERT, UPDATE, DELETE ON tracks, markers, waypoints TO coop_rls;

ALTER TABLE tracks FORCE ROW LEVEL SECURITY;
ALTER TABLE tracks ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tracks_select ON tracks;
CREATE POLICY tracks_select ON tracks FOR SELECT USING (coop_can_view_group(group_id));
DROP POLICY IF EXISTS tracks_insert ON tracks;
CREATE POLICY tracks_insert ON tracks FOR INSERT WITH CHECK (coop_is_member(group_id));
DROP POLICY IF EXISTS tracks_update ON tracks;
CREATE POLICY tracks_update ON tracks FOR UPDATE USING (owner_id = coop_current_sub() OR coop_is_owner(group_id));
DROP POLICY IF EXISTS tracks_delete ON tracks;
CREATE POLICY tracks_delete ON tracks FOR DELETE USING (owner_id = coop_current_sub() OR coop_is_owner(group_id));

ALTER TABLE markers FORCE ROW LEVEL SECURITY;
ALTER TABLE markers ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS markers_select ON markers;
CREATE POLICY markers_select ON markers FOR SELECT USING (coop_can_view_group(group_id));
DROP POLICY IF EXISTS markers_insert ON markers;
CREATE POLICY markers_insert ON markers FOR INSERT WITH CHECK (coop_is_member(group_id));
DROP POLICY IF EXISTS markers_update ON markers;
CREATE POLICY markers_update ON markers FOR UPDATE USING (owner_id = coop_current_sub() OR coop_is_owner(group_id));
DROP POLICY IF EXISTS markers_delete ON markers;
CREATE POLICY markers_delete ON markers FOR DELETE USING (owner_id = coop_current_sub() OR coop_is_owner(group_id));

ALTER TABLE waypoints FORCE ROW LEVEL SECURITY;
ALTER TABLE waypoints ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS waypoints_select ON waypoints;
CREATE POLICY waypoints_select ON waypoints FOR SELECT USING (coop_can_view_group(group_id));
DROP POLICY IF EXISTS waypoints_insert ON waypoints;
CREATE POLICY waypoints_insert ON waypoints FOR INSERT WITH CHECK (coop_is_member(group_id));
DROP POLICY IF EXISTS waypoints_update ON waypoints;
CREATE POLICY waypoints_update ON waypoints FOR UPDATE USING (owner_id = coop_current_sub() OR coop_is_owner(group_id));
DROP POLICY IF EXISTS waypoints_delete ON waypoints;
CREATE POLICY waypoints_delete ON waypoints FOR DELETE USING (owner_id = coop_current_sub() OR coop_is_owner(group_id));

-- ---------------------------------------------------------------------------
-- Tier-2 contribution ledger (docs/design/tier2-entry-model.md).
--   SELECT = member/owner/creator of the group (coop_can_view_group)
--   INSERT = any member of the group
--   UPDATE = any member (it carries the state transitions: proposed ->
--            countersigned -> ratified/rejected/superseded/expired)
--   DELETE = NO POLICY, ON PURPOSE. With FORCE RLS and no delete policy the app
--            role cannot delete an entry at all — "entries are never edited and
--            never deleted" (§7 invariant 8) is enforced HERE, not by convention.
-- Content immutability is cryptographic rather than policy: entry_id IS the hash
-- of the signed body, so an edited body stops matching the id every counterparty
-- already holds, and the counter-signatures stop verifying.
-- Signatures are append-only: INSERT as a member, and NO update/delete policy at
-- all. group_id is denormalized onto tier2_signature so these policies can match
-- the waypoint pattern.
-- anchors — ONE stream for every family that asks for a periodic root (tier2,
-- custody, coverage). System/operator-written (no user write policy, like
-- telephony_resources); readable where the group is viewable, and federation-wide
-- rows (group_id IS NULL) are readable by any authenticated member: they are
-- PUBLISHED roots, not group content.
-- ---------------------------------------------------------------------------
GRANT SELECT, INSERT, UPDATE ON tier2_entry TO coop_rls;
GRANT SELECT, INSERT ON tier2_signature TO coop_rls;
GRANT SELECT, INSERT, UPDATE ON anchors TO coop_rls;

ALTER TABLE tier2_entry FORCE ROW LEVEL SECURITY;
ALTER TABLE tier2_entry ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tier2_entry_select ON tier2_entry;
CREATE POLICY tier2_entry_select ON tier2_entry FOR SELECT USING (coop_can_view_group(group_id));
DROP POLICY IF EXISTS tier2_entry_insert ON tier2_entry;
CREATE POLICY tier2_entry_insert ON tier2_entry FOR INSERT WITH CHECK (coop_is_member(group_id));
DROP POLICY IF EXISTS tier2_entry_update ON tier2_entry;
CREATE POLICY tier2_entry_update ON tier2_entry FOR UPDATE USING (coop_is_member(group_id));

ALTER TABLE tier2_signature FORCE ROW LEVEL SECURITY;
ALTER TABLE tier2_signature ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tier2_signature_select ON tier2_signature;
CREATE POLICY tier2_signature_select ON tier2_signature FOR SELECT USING (coop_can_view_group(group_id));
DROP POLICY IF EXISTS tier2_signature_insert ON tier2_signature;
CREATE POLICY tier2_signature_insert ON tier2_signature FOR INSERT WITH CHECK (coop_is_member(group_id));

ALTER TABLE anchors FORCE ROW LEVEL SECURITY;
ALTER TABLE anchors ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS anchors_select ON anchors;
CREATE POLICY anchors_select ON anchors FOR SELECT USING (group_id IS NULL OR coop_can_view_group(group_id));

-- ---------------------------------------------------------------------------
-- Anchoring (docs/design/sharded-ledgers-and-anchors.md §5). anchors has NO user
-- write policy, so neither the app role nor a member can mint or alter a root: the
-- three functions below are SECURITY DEFINER, owned by coop_rls (BYPASSRLS), locked
-- to coop_ops, and reachable only by the operator pool — the same shape as
-- coop_provision_telephony_resource.
--
-- Why a read function at all: the anchoring job is a node-operator task, not a member
-- request, so it holds no app.sub and RLS would hide the ledger from it. It reads
-- ENTRY IDS ONLY — commitments, never content — which is all a tree needs.
-- ---------------------------------------------------------------------------

-- The period's entry ids, in seq order. Order is part of the commitment, so the
-- ORDER BY is load-bearing: the same rows in another order produce another root.
CREATE OR REPLACE FUNCTION coop_tier2_period_ids(p_group_id uuid, p_period date)
RETURNS TABLE(entry_id text, seq bigint)
SECURITY DEFINER SET search_path = public AS $$
  SELECT e.entry_id, e.seq
    FROM tier2_entry e
   WHERE e.group_id = p_group_id
     AND e.period = p_period
   ORDER BY e.seq
$$ LANGUAGE sql STABLE;
ALTER FUNCTION coop_tier2_period_ids(uuid, date) OWNER TO coop_rls;
REVOKE EXECUTE ON FUNCTION coop_tier2_period_ids(uuid, date) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION coop_tier2_period_ids(uuid, date) TO coop_ops;

-- Every group root already anchored for a period, excluding the federation row
-- itself (which must never be a leaf of its own tree).
CREATE OR REPLACE FUNCTION coop_tier2_roots_for_period(p_period date)
RETURNS TABLE(scope_id text, root text)
SECURITY DEFINER SET search_path = public AS $$
  SELECT a.scope_id, a.root
    FROM anchors a
   WHERE a.family = 'tier2'
     AND a.period = p_period
     AND a.scope_id <> 'federation'
   ORDER BY a.scope_id
$$ LANGUAGE sql STABLE;
ALTER FUNCTION coop_tier2_roots_for_period(date) OWNER TO coop_rls;
REVOKE EXECUTE ON FUNCTION coop_tier2_roots_for_period(date) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION coop_tier2_roots_for_period(date) TO coop_ops;

-- Claim an anchor slot. IDEMPOTENT and first-writer-wins: re-anchoring the same root
-- is a no-op returning conflict=false, while a DIFFERENT root for the same
-- (family, scope, period) comes back flagged conflict=true. A conflicting anchor is
-- an alarm, not a race — it means two parties disagree about a period's history.
CREATE OR REPLACE FUNCTION coop_anchor_slot(
  p_family     text,
  p_group_id   uuid,
  p_scope_id   text,
  p_period     date,
  p_root       text,
  p_leaf_count int
) RETURNS TABLE(root text, leaf_count int, conflict boolean)
SECURITY DEFINER SET search_path = public AS $$
BEGIN
  IF session_user NOT IN ('postgres', 'coop_ops') THEN
    RAISE EXCEPTION 'coop_anchor_slot: operator-only (session_user=%)', session_user;
  END IF;
  IF p_leaf_count < 1 THEN
    RAISE EXCEPTION 'coop_anchor_slot: refusing an empty root (leaf_count=%)', p_leaf_count;
  END IF;
  INSERT INTO anchors (family, group_id, scope_id, period, root, leaf_count)
  VALUES (p_family, p_group_id, p_scope_id, p_period, p_root, p_leaf_count)
  ON CONFLICT (family, scope_id, period) DO NOTHING;
  RETURN QUERY
    SELECT a.root, a.leaf_count, (a.root IS DISTINCT FROM p_root)
      FROM anchors a
     WHERE a.family = p_family AND a.scope_id = p_scope_id AND a.period = p_period;
END;
$$ LANGUAGE plpgsql;
ALTER FUNCTION coop_anchor_slot(text, uuid, text, date, text, int) OWNER TO coop_rls;
REVOKE EXECUTE ON FUNCTION coop_anchor_slot(text, uuid, text, date, text, int) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION coop_anchor_slot(text, uuid, text, date, text, int) TO coop_ops;

-- ---------------------------------------------------------------------------
-- Dues (docs/design/tier2-entry-model.md §5.1). The load-bearing rule is the WAIVER
-- policy below: "this member was waived" is a MODE LEAK, so a waiver row is readable
-- only by the member it concerns and by holders of the bookkeeping grant — never by
-- the group at large. The group sees the count, which the API derives separately.
--
-- dues_policy has NO user write policy: a policy is adopted by a decision, and letting
-- a member INSERT one directly would let a treasurer change what everyone owes without
-- a vote. Writes go through the decision path.
-- ---------------------------------------------------------------------------
GRANT SELECT ON dues_policy TO coop_rls;
GRANT SELECT, INSERT, DELETE ON dues_waiver TO coop_rls;

ALTER TABLE dues_policy FORCE ROW LEVEL SECURITY;
ALTER TABLE dues_policy ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS dues_policy_select ON dues_policy;
CREATE POLICY dues_policy_select ON dues_policy FOR SELECT USING (coop_can_view_group(group_id));


-- ---------------------------------------------------------------------------
ALTER TABLE dues_policy ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS dues_policy_select ON dues_policy;
CREATE POLICY dues_policy_select ON dues_policy FOR SELECT USING (coop_can_view_group(group_id));


-- ---------------------------------------------------------------------------

-- ---------------------------------------------------------------------------
-- coop_rail_event_count — "has a verified delivery EVER arrived?" as a fact.
-- rail_event is FORCE RLS with NO policies on purpose (nobody should read the provider's own
-- words about payments), so the app role sees zero rows and a plain count is blind to its own
-- evidence. A definer function returning a bare count leaks nothing — no row, no attribution.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION coop_rail_event_count() RETURNS bigint
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $railcount$
  SELECT count(*) FROM rail_event
$railcount$;
ALTER FUNCTION coop_rail_event_count() OWNER TO coop_rls;
REVOKE EXECUTE ON FUNCTION coop_rail_event_count() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION coop_rail_event_count() TO coop;

-- ---------------------------------------------------------------------------
-- coop_rails_settle — the ONLY writer for a rail webhook. A webhook is untrusted input from
-- outside, and the intent row is RLS-protected, so a system write with no member identity must
-- go through a definer function rather than being handed an RLS exemption. It dedupes on
-- (rail, event_id) so a provider retry is a no-op, and it refuses to move an intent backwards.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION coop_rails_settle(
  p_rail text, p_provider_ref text, p_status text, p_received numeric,
  p_event_id text, p_event_type text
) RETURNS TABLE (dup boolean, intent_id uuid, group_id uuid, payer_sub text, cur_status text, received numeric)
SECURITY DEFINER SET search_path = public AS $settle$
DECLARE v_intent payment_intent%ROWTYPE; v_ins int;
BEGIN
  INSERT INTO rail_event (rail, event_id, event_type, provider_ref, status, received)
  VALUES (p_rail, p_event_id, p_event_type, p_provider_ref, p_status, p_received)
  ON CONFLICT (rail, event_id) DO NOTHING;
  GET DIAGNOSTICS v_ins = ROW_COUNT;
  IF v_ins = 0 THEN
    RETURN QUERY SELECT true, NULL::uuid, NULL::uuid, NULL::text, NULL::text, NULL::numeric;
    RETURN;
  END IF;

  SELECT * INTO v_intent FROM payment_intent
   WHERE rail = p_rail AND provider_ref = p_provider_ref LIMIT 1;
  IF NOT FOUND THEN
    RETURN QUERY SELECT false, NULL::uuid, NULL::uuid, NULL::text, NULL::text, NULL::numeric;
    RETURN;
  END IF;
  -- RECORD-ONLY. An informational event (order created, a bridge moving) carries a provider_ref
  -- and so DOES match here, but has no status: without this guard it would fall through to the
  -- ELSE below and null out a perfectly good intent status.
  IF p_status IS NULL THEN
    UPDATE rail_event SET intent_id = v_intent.id WHERE rail = p_rail AND event_id = p_event_id;
    RETURN QUERY SELECT false, v_intent.id, v_intent.group_id, v_intent.payer_sub, v_intent.status, v_intent.received_amount;
    RETURN;
  END IF;

  IF v_intent.status = 'reversed' THEN
    -- already taken back; a later settle notice must not resurrect it
    RETURN QUERY SELECT false, v_intent.id, v_intent.group_id, v_intent.payer_sub, v_intent.status, v_intent.received_amount;
    RETURN;
  END IF;

  IF p_status IN ('settled','partial') THEN
    UPDATE payment_intent
       SET status = p_status,
           received_amount = COALESCE(p_received, received_amount),
           settled_at = COALESCE(settled_at, now()),
           updated_at = now()
     WHERE id = v_intent.id;
  ELSIF p_status = 'reversed' THEN
    UPDATE payment_intent SET status = 'reversed', updated_at = now() WHERE id = v_intent.id;
  ELSE
    -- cancelled / failed only ever apply to something that has not settled
    UPDATE payment_intent SET status = p_status, updated_at = now()
     WHERE id = v_intent.id AND status = 'pending';
  END IF;

  UPDATE rail_event SET intent_id = v_intent.id WHERE rail = p_rail AND event_id = p_event_id;
  RETURN QUERY SELECT false, v_intent.id, v_intent.group_id, v_intent.payer_sub,
    (SELECT status FROM payment_intent WHERE id = v_intent.id), p_received;
END;
$settle$ LANGUAGE plpgsql;
ALTER FUNCTION coop_rails_settle(text, text, text, numeric, text, text) OWNER TO coop_rls;
REVOKE EXECUTE ON FUNCTION coop_rails_settle(text, text, text, numeric, text, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION coop_rails_settle(text, text, text, numeric, text, text) TO coop;

-- ---------------------------------------------------------------------------
-- rail_event — the provider's own words about a payment, and the dedupe behind it.
-- FORCE RLS with NO user policies on purpose: a webhook log is not something any application
-- role should read, and the settlement function (owned by coop_rls, BYPASSRLS) is the only
-- reader and writer. The GRANT matters as much as the policy: a SECURITY DEFINER function
-- runs as its OWNER, so without it the function cannot write the table it exists to write.
-- ---------------------------------------------------------------------------
ALTER TABLE rail_event ENABLE ROW LEVEL SECURITY;
ALTER TABLE rail_event FORCE ROW LEVEL SECURITY;
GRANT SELECT, INSERT, UPDATE ON rail_event TO coop_rls;

-- payment_intent — payment attribution. Deliberately NOT group-readable: the dues rule
-- is that which mode satisfied an obligation, how much, and from whom are visible to
-- NOBODY, and a card payment is the loudest of those modes. The payer sees their own;
-- the bookkeeper grant sees the group's; the group sees neither.
-- ---------------------------------------------------------------------------
ALTER TABLE payment_intent ENABLE ROW LEVEL SECURITY;
ALTER TABLE payment_intent FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS payment_intent_select ON payment_intent;
CREATE POLICY payment_intent_select ON payment_intent
  FOR SELECT USING (payer_sub = coop_current_sub() OR coop_has_grant(group_id, 'dues.bookkeep'));
DROP POLICY IF EXISTS payment_intent_insert ON payment_intent;
CREATE POLICY payment_intent_insert ON payment_intent
  FOR INSERT WITH CHECK (payer_sub = coop_current_sub() AND coop_is_member(group_id));
DROP POLICY IF EXISTS payment_intent_update ON payment_intent;
CREATE POLICY payment_intent_update ON payment_intent
  FOR UPDATE USING (payer_sub = coop_current_sub() OR coop_has_grant(group_id, 'dues.bookkeep'));
GRANT SELECT, INSERT, UPDATE ON payment_intent TO coop_rls;

ALTER TABLE dues_waiver FORCE ROW LEVEL SECURITY;
ALTER TABLE dues_waiver ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS dues_waiver_select ON dues_waiver;
CREATE POLICY dues_waiver_select ON dues_waiver FOR SELECT
  USING (sub = coop_current_sub() OR coop_has_grant(group_id, 'dues.bookkeep'));
DROP POLICY IF EXISTS dues_waiver_insert ON dues_waiver;
CREATE POLICY dues_waiver_insert ON dues_waiver FOR INSERT
  WITH CHECK (coop_has_grant(group_id, 'dues.bookkeep'));
DROP POLICY IF EXISTS dues_waiver_delete ON dues_waiver;
CREATE POLICY dues_waiver_delete ON dues_waiver FOR DELETE
  USING (coop_has_grant(group_id, 'dues.bookkeep'));

-- The group sees the COUNT, never the mode. A per-row read is impossible for a plain
-- member (the RLS policy above), so the aggregate is its own function rather than a
-- query — count-only, and guarded by `coop_can_view_group` so a non-member gets nothing.
--
-- NOTE the deliberate asymmetry with every other definer function in this file: this one
-- is NOT revoked from PUBLIC, because it is meant to be callable by an ordinary member.
-- It is safe to do so precisely because it returns a number of waivers per obligation and
-- nothing else — no sub, no reason, no period detail.
CREATE OR REPLACE FUNCTION coop_dues_waiver_counts(p_group_id uuid, p_from date, p_to date)
RETURNS TABLE(obligation text, n int)
SECURITY DEFINER SET search_path = public AS $$
  SELECT w.obligation, count(*)::int
    FROM dues_waiver w
   WHERE w.group_id = p_group_id
     AND w.period >= p_from
     AND w.period <= p_to
     -- MEMBERSHIP, not viewability: coop_can_view_group is true for ANYONE on a group
     -- with privacy='open', which would publish the waiver count to outsiders. §5.1 gives
     -- the aggregate to THE GROUP.
     AND coop_is_member(p_group_id)
   GROUP BY w.obligation
   ORDER BY w.obligation
$$ LANGUAGE sql STABLE;
ALTER FUNCTION coop_dues_waiver_counts(uuid, date, date) OWNER TO coop_rls;
