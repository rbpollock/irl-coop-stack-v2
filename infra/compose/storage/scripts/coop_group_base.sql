-- irl.coop — one base per group (settled model: "a base is a group's data surface").
--
-- Each group gets a dedicated schema (grp_<uuid-hex>) holding *narrowed*
-- security_invoker views over the projection, scoped to exactly that group.
-- Two layers of scoping, defense in depth:
--   1. WHERE group_id = <this group>  — the "shape": this base shows only this group.
--   2. security_invoker = true          — RLS still fires under the viewer's identity,
--                                          so a NON-member (or an open-group stranger)
--                                          sees nothing even though the view narrows to
--                                          a group they don't belong to.
--
-- A NocoDB base per group mounts its schema as an external source
-- (searchPath = [grp_<hex>]). Provisioned on group create AND backfillable.

-- Re-runnable, operator-invoked (SECURITY DEFINER = postgres; needs CREATE SCHEMA).
CREATE OR REPLACE FUNCTION coop_provision_group_base(p_group_id uuid)
RETURNS text
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql AS $$
DECLARE
  v_schema text := 'grp_' || replace(p_group_id::text, '-', '');
  v_name   text;
BEGIN
  SELECT name INTO v_name FROM groups WHERE id = p_group_id;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'coop_provision_group_base: no group %', p_group_id;
  END IF;

  EXECUTE format('CREATE SCHEMA IF NOT EXISTS %I', v_schema);
  EXECUTE format('GRANT USAGE ON SCHEMA %I TO coop_member', v_schema);
  EXECUTE format('GRANT USAGE ON SCHEMA %I TO coop_rls', v_schema);

  -- groups: just this group's own record.
  EXECUTE format($v$
    CREATE OR REPLACE VIEW %1$I.groups WITH (security_invoker = true) AS
      SELECT id, name, description, privacy, kind, slug, safe_address, created_at, updated_at
        FROM groups WHERE id = %2$L::uuid
  $v$, v_schema, p_group_id);

  -- group_members: this group's seats (join for name is redundant but harmless).
  EXECUTE format($v$
    CREATE OR REPLACE VIEW %1$I.group_members WITH (security_invoker = true) AS
      SELECT gm.group_id, gm.sub, gm.roles, gm.alias, gm.visibility, gm.created_at
        FROM group_members gm WHERE gm.group_id = %2$L::uuid
  $v$, v_schema, p_group_id);

  -- resource_scopes: this group's scoped apps/resources.
  EXECUTE format($v$
    CREATE OR REPLACE VIEW %1$I.resource_scopes WITH (security_invoker = true) AS
      SELECT rs.group_id, rs.app, rs.resource_key, rs.scoped_by, rs.scoped_at
        FROM resource_scopes rs WHERE rs.group_id = %2$L::uuid
  $v$, v_schema, p_group_id);

  -- events: this group's activity stream.
  EXECUTE format($v$
    CREATE OR REPLACE VIEW %1$I.events WITH (security_invoker = true) AS
      SELECT id, group_id, source, source_event_id, type, payload, occurred_at, created_at
        FROM events WHERE group_id = %2$L::uuid
  $v$, v_schema, p_group_id);

  -- dues_policy: this group's policy (may be none — empty set, not an error).
  EXECUTE format($v$
    CREATE OR REPLACE VIEW %1$I.dues_policy WITH (security_invoker = true) AS
      SELECT id, group_id, version, cadence, grace_days, obligations, waiver, status, decided_by, created_at
        FROM dues_policy WHERE group_id = %2$L::uuid
  $v$, v_schema, p_group_id);

  -- dues_waiver: this group's waivers (RLS still limits to self/bookkeeper).
  EXECUTE format($v$
    CREATE OR REPLACE VIEW %1$I.dues_waiver WITH (security_invoker = true) AS
      SELECT id, group_id, sub, period, obligation, granted_by, authority, note, created_at
        FROM dues_waiver WHERE group_id = %2$L::uuid
  $v$, v_schema, p_group_id);

  -- tier2 ledger + signatures: this group's entries.
  EXECUTE format($v$
    CREATE OR REPLACE VIEW %1$I.tier2_entry WITH (security_invoker = true) AS
      SELECT entry_id, group_id, seq, prev, period, kind, subject, subject_kind,
             counterparty, scope, quantity, unit, happened_at, recorded_at, late,
             payload, refs, state, created_by
        FROM tier2_entry WHERE group_id = %2$L::uuid
  $v$, v_schema, p_group_id);

  EXECUTE format($v$
    CREATE OR REPLACE VIEW %1$I.tier2_signature WITH (security_invoker = true) AS
      SELECT entry_id, group_id, signer, class, authority, valid_from, valid_to, signed_at, sig
        FROM tier2_signature WHERE group_id = %2$L::uuid
  $v$, v_schema, p_group_id);

  -- payment_intent: this group's intents (RLS still limits to payer/bookkeeper).
  EXECUTE format($v$
    CREATE OR REPLACE VIEW %1$I.payment_intent WITH (security_invoker = true) AS
      SELECT id, group_id, payer_sub, rail, provider_ref, amount, currency, destination,
             status, received_amount, pay_url, created_at, settled_at
        FROM payment_intent WHERE group_id = %2$L::uuid
  $v$, v_schema, p_group_id);

  -- telephony_resources: this group's DIDs/extensions.
  EXECUTE format($v$
    CREATE OR REPLACE VIEW %1$I.telephony_resources WITH (security_invoker = true) AS
      SELECT id, group_id, group_telephony_id, resource_type, external_ref, config, created_at
        FROM telephony_resources WHERE group_id = %2$L::uuid
  $v$, v_schema, p_group_id);

  -- SELECT on every view in this schema to coop_member (member roles inherit).
  EXECUTE format(
    'GRANT SELECT ON ALL TABLES IN SCHEMA %I TO coop_member', v_schema);

  RETURN v_schema;
END;
$$;

-- coop-api (connects as coop) must be able to trigger provisioning on group create.
GRANT EXECUTE ON FUNCTION coop_provision_group_base(uuid) TO coop, coop_ops;
REVOKE EXECUTE ON FUNCTION coop_provision_group_base(uuid) FROM PUBLIC;

-- ============================================================================
-- Personal base = the LENS (B2). A personal group's base is the member's view
-- across ALL the groups they belong to — NOT narrowed to the (near-empty)
-- personal group. Federation = RLS scoping: each federated view is a
-- security_invoker projection over the global *_view relations, so RLS fires
-- under the member's cert role and returns exactly their slice across groups.
-- A personal group has no events/dues/resources of its own, so a group-narrowed
-- view would be empty — hence this distinct shape.
-- ============================================================================

CREATE OR REPLACE FUNCTION coop_provision_personal_base(p_group_id uuid)
RETURNS text
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql AS $$
DECLARE
  v_schema text := 'grp_' || replace(p_group_id::text, '-', '');
  v_kind   text;
BEGIN
  SELECT kind INTO v_kind FROM groups WHERE id = p_group_id;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'coop_provision_personal_base: no group %', p_group_id;
  END IF;
  IF v_kind <> 'personal' THEN
    RAISE EXCEPTION 'coop_provision_personal_base: group % is kind %, not personal', p_group_id, v_kind;
  END IF;

  EXECUTE format('CREATE SCHEMA IF NOT EXISTS %I', v_schema);
  EXECUTE format('GRANT USAGE ON SCHEMA %I TO coop_member', v_schema);
  EXECUTE format('GRANT USAGE ON SCHEMA %I TO coop_rls', v_schema);

  -- The schema may already hold the group-NARROWED views (coop_provision_group_base
  -- ran over every group during the backfill). CREATE OR REPLACE cannot rename or
  -- reorder columns, so drop the stale shape first. We only ever replace views
  -- this function owns (all views in the schema are provisioned, not user-made).
  EXECUTE format($v$
    DO $d$
    DECLARE r record;
    BEGIN
      FOR r IN
        SELECT c.relname AS v
          FROM pg_class c
          JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = %1$L AND c.relkind IN ('v','m')
      LOOP
        EXECUTE format('DROP VIEW IF EXISTS %%I.%%I', %1$L, r.v);
      END LOOP;
    END
    $d$;
  $v$, v_schema);

  -- Federated lens: each view re-projects the matching global *_view relation.
  -- No group WHERE — RLS is the only scoping, keyed to the member's cert role.
  -- security_invoker chains: the inner global view also runs as the member.
  EXECUTE format($v$
    CREATE OR REPLACE VIEW %1$I.groups WITH (security_invoker = true) AS
      SELECT id, name, description, privacy, kind, slug, safe_address, created_at, updated_at
        FROM public.groups_view
  $v$, v_schema);

  EXECUTE format($v$
    CREATE OR REPLACE VIEW %1$I.group_members WITH (security_invoker = true) AS
      SELECT group_id, group_name, sub, roles, alias, visibility, created_at
        FROM public.group_members_view
  $v$, v_schema);

  EXECUTE format($v$
    CREATE OR REPLACE VIEW %1$I.resource_scopes WITH (security_invoker = true) AS
      SELECT group_id, group_name, app, resource_key, scoped_by, scoped_at
        FROM public.resource_scopes_view
  $v$, v_schema);

  EXECUTE format($v$
    CREATE OR REPLACE VIEW %1$I.events WITH (security_invoker = true) AS
      SELECT id, group_id, source, source_event_id, type, payload, occurred_at, created_at
        FROM public.events_view
  $v$, v_schema);

  EXECUTE format($v$
    CREATE OR REPLACE VIEW %1$I.notification_reads WITH (security_invoker = true) AS
      SELECT user_sub, event_id, read_at, cleared_at
        FROM public.notification_reads_view
  $v$, v_schema);

  EXECUTE format($v$
    CREATE OR REPLACE VIEW %1$I.notification_digests WITH (security_invoker = true) AS
      SELECT user_sub, event_id, sent_at
        FROM public.notification_digests_view
  $v$, v_schema);

  EXECUTE format($v$
    CREATE OR REPLACE VIEW %1$I.profiles WITH (security_invoker = true) AS
      SELECT sub, email, display_name, avatar, onboarded, onboarded_at, offerings, created_at, updated_at
        FROM public.profiles_view
  $v$, v_schema);

  EXECUTE format($v$
    CREATE OR REPLACE VIEW %1$I.dues_policy WITH (security_invoker = true) AS
      SELECT id, group_id, version, cadence, grace_days, obligations, waiver, status, decided_by, created_at
        FROM public.dues_policy_view
  $v$, v_schema);

  EXECUTE format($v$
    CREATE OR REPLACE VIEW %1$I.dues_waiver WITH (security_invoker = true) AS
      SELECT id, group_id, sub, period, obligation, granted_by, authority, note, created_at
        FROM public.dues_waiver_view
  $v$, v_schema);

  EXECUTE format($v$
    CREATE OR REPLACE VIEW %1$I.tier2_entry WITH (security_invoker = true) AS
      SELECT entry_id, group_id, seq, prev, period, kind, subject, subject_kind,
             counterparty, scope, quantity, unit, happened_at, recorded_at, late,
             payload, refs, state, created_by
        FROM public.tier2_entry_view
  $v$, v_schema);

  EXECUTE format($v$
    CREATE OR REPLACE VIEW %1$I.tier2_signature WITH (security_invoker = true) AS
      SELECT entry_id, group_id, signer, class, authority, valid_from, valid_to, signed_at, sig
        FROM public.tier2_signature_view
  $v$, v_schema);

  EXECUTE format($v$
    CREATE OR REPLACE VIEW %1$I.payment_intent WITH (security_invoker = true) AS
      SELECT id, group_id, payer_sub, rail, provider_ref, amount, currency, destination,
             status, received_amount, pay_url, created_at, settled_at
        FROM public.payment_intent_view
  $v$, v_schema);

  EXECUTE format($v$
    CREATE OR REPLACE VIEW %1$I.telephony_resources WITH (security_invoker = true) AS
      SELECT id, group_id, group_telephony_id, resource_type, external_ref, config, created_at
        FROM public.telephony_resources_view
  $v$, v_schema);

  EXECUTE format(
    'GRANT SELECT ON ALL TABLES IN SCHEMA %I TO coop_member', v_schema);

  RETURN v_schema;
END;
$$;

GRANT EXECUTE ON FUNCTION coop_provision_personal_base(uuid) TO coop, coop_ops;
REVOKE EXECUTE ON FUNCTION coop_provision_personal_base(uuid) FROM PUBLIC;
