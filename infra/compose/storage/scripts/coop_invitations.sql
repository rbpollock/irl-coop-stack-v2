-- ---
-- coop_invitations.sql — the door engine (slice-1 schema), Citus `irlcoop`.
-- Vocabulary (see docs/design/invitation-and-join-mechanism.md §0): an invite is a
-- *thing passed* (a tie); membership = holding the Safe = owner; a non-member is a guest
-- with temporary scoped access. "Seat"/"door"/"key" do not appear in user surface.
--
-- Identity = `app.sub` (coop_current_sub(), the session GUC set by coop-api) — the same
-- FORCE RLS discipline as the rest of the stack (no app-level bypass).
--
-- Three tables:
--   invitations        — a named tie offered to one canonical email (member_offer
--                         signals the "also hold the Safe" offer; gate is explicit).
--   open_invitations   — a bounded, self-service intake (the open invitation).
--   join_requests      -- a person asking to join a group.
-- Plus a SECURITY DEFINER redeem that makes redemption single-use + server-authoritative.
--
-- Idempotent: CREATE ... IF NOT EXISTS / OR REPLACE; safe to run at provider.

BEGIN;

-- ---------------------------------------------------------------------------
-- invitations — a proposed, directed tie
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS invitations (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  group_id      uuid NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
  to_email      text NOT NULL,                 -- canonical, lowercased by caller
  to_sub        text,                          -- pre-known identity (if any)
  subject       text,                          -- the verb: doc | project | offer | call | ...
  subject_ref   text,                          -- the target of the verb
  member_offer  boolean NOT NULL DEFAULT false,            -- also offer admission to the Safe
  roles         text[] NOT NULL DEFAULT ARRAY['member'],   -- may-assign per inviter-role
  message       text,
  status        text NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending','accepted','declined','revoked','expired')),
  nonce         text UNIQUE NOT NULL,          -- bound to the URL token
  expires_at    timestamptz,
  created_by    text NOT NULL,
  redeemed_by   text,
  redeemed_at   timestamptz,
  created_at    timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE invitations ENABLE ROW LEVEL SECURITY;
ALTER TABLE invitations FORCE ROW LEVEL SECURITY;

-- owner/inviter can see and manage the invites they hold
CREATE POLICY invites_owner_all ON invitations
  FOR ALL TO PUBLIC
  USING (created_by = coop_current_sub() OR coop_is_owner(group_id))
  WITH CHECK (created_by = coop_current_sub() OR coop_is_owner(group_id));

-- a bound identity can see the tie offered to them (after redemption it is theirs)
CREATE POLICY invites_subject_sel ON invitations
  FOR SELECT TO PUBLIC
  USING (redeemed_by = coop_current_sub());

-- ---------------------------------------------------------------------------
-- open_invitations — a bounded, self-service intake (the open invitation)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS open_invitations (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  group_id    uuid NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
  cap         int  NOT NULL CHECK (cap > 0),
  remaining   int  NOT NULL,
  scope       text NOT NULL,                -- what the intake admits (scoped verb)
  subgroup_id uuid,
  expires_at  timestamptz,
  created_by  text NOT NULL,
  revoked     boolean NOT NULL DEFAULT false,
  created_at  timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE open_invitations ENABLE ROW LEVEL SECURITY;
ALTER TABLE open_invitations FORCE ROW LEVEL SECURITY;

CREATE POLICY open_invitations_owner ON open_invitations
  FOR ALL TO PUBLIC
  USING (coop_is_owner(group_id))
  WITH CHECK (coop_is_owner(group_id));

-- ---------------------------------------------------------------------------
-- join_requests — a person asks to be tied in
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS join_requests (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  group_id     uuid NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
  sub          text NOT NULL,
  status       text NOT NULL DEFAULT 'pending'
               CHECK (status IN ('pending','accepted','declined')),
  decided_by   text,
  decided_at   timestamptz,
  created_at   timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE join_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE join_requests FORCE ROW LEVEL SECURITY;

CREATE POLICY join_req_owners ON join_requests
  FOR ALL TO PUBLIC
  USING (coop_is_owner(group_id))
  WITH CHECK (coop_is_owner(group_id));
CREATE POLICY join_req_self_sel ON join_requests
  FOR SELECT TO PUBLIC
  USING (sub = coop_current_sub());

-- ---------------------------------------------------------------------------
-- redeem — single-use, server-authoritative admission
-- ---------------------------------------------------------------------------
-- Called with the caller's identity already bound (the app verifies the signed token
-- against its canonical email). The function owns the LAST say on state: it locks
-- the row, refuses already-accepted/revoked/expired, marks accepted, and if the invite
-- offered membership (member_offer) it seats the person as a group member.
-- SECURITY DEFINER (owned by coop_rls, BYPASSRLS) so it may write group_members too.
CREATE OR REPLACE FUNCTION coop_invite_redeem(p_invite_id uuid, p_sub text)
RETURNS text
SECURITY DEFINER SET search_path = public
AS $$
DECLARE
  r invitations;
  seated boolean := false;
BEGIN
  SELECT * INTO r FROM invitations WHERE id = p_invite_id FOR UPDATE;
  IF NOT FOUND THEN
    RETURN 'missing';
  END IF;
  IF r.status <> 'pending' THEN
    RETURN 'not-pending';             -- already redeemed/revoked/declined (single-use)
  END IF;
  IF r.expires_at IS NOT NULL AND r.expires_at < now() THEN
    RETURN 'expired';
  END IF;

  UPDATE invitations
     SET status = 'accepted', redeemed_by = p_sub, redeemed_at = now()
   WHERE id = p_invite_id;

  IF r.member_offer THEN
    -- admission as an owner (key) -> membership in the group.
    INSERT INTO group_members (group_id, sub, roles, holder_kind)
    VALUES (r.group_id, p_sub, r.roles, 'person')
    ON CONFLICT (group_id, holder_key)
    DO UPDATE SET roles = COALESCE(EXCLUDED.roles, group_members.roles);
    seated := true;
  END IF;

  IF seated THEN RETURN 'seated'; ELSE RETURN 'accepted'; END IF;
END
$$ LANGUAGE plpgsql;
ALTER FUNCTION coop_invite_redeem(uuid, text) OWNER TO coop_rls;

GRANT SELECT, INSERT, UPDATE, DELETE ON invitations, open_invitations, join_requests TO coop_rls;
GRANT SELECT, INSERT, UPDATE, DELETE ON invitations, open_invitations, join_requests TO coop;
GRANT SELECT, INSERT, UPDATE ON invitations, open_invitations, join_requests TO coop_app;
GRANT SELECT, INSERT, UPDATE ON invitations, open_invitations, join_requests TO coop_member;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO coop_rls;

COMMIT;