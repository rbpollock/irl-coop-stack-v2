#!/usr/bin/env python3
"""Sync group membership -> NocoDB base access.

One base per group: a base's NocoDB members MUST mirror the group's members,
or the gate SSO user can't open their own base (403). Canonical email = Keycloak
email (what the gate forwards as x-forwarded-email), keyed by sub = Keycloak id.

Emits JSON grant rows: {base_id, email, role}. Pipe into
sync-base-members.mjs (browser runner, posts to /api/v2/meta/bases/:id/users).
"""
import json, subprocess, sys


def psql(db, sql):
    return subprocess.run(
        ["docker", "exec", "storage-postgres-1", "psql", "-U", "postgres",
         "-d", db, "-tAc", sql],
        capture_output=True, text=True, check=True,
    ).stdout


def main():
    # sub -> canonical email (Keycloak). Keycloak id IS the OIDC sub.
    sub_email = {}
    for line in psql("keycloak",
                     "SELECT id || '|' || email FROM user_entity WHERE email IS NOT NULL").splitlines():
        if "|" in line:
            sid, email = line.strip().split("|", 1)
            sub_email[sid] = email

    # group id -> schema (grp_<uuid-hex>, deterministic)
    schema_of = {}
    for line in psql("irlcoop",
                     "SELECT id || '|' || ('grp_'||replace(id::text,'-','')) FROM groups").splitlines():
        if "|" in line:
            gid, schema = line.strip().split("|", 1)
            schema_of[gid] = schema

    # base id -> source alias (schema)
    base_of = {}
    for line in psql("nocodb",
                     "SELECT b.id || '|' || s.alias FROM nc_bases_v2 b "
                     "JOIN nc_sources_v2 s ON s.base_id=b.id "
                     "WHERE b.deleted IS DISTINCT FROM true AND b.is_meta IS DISTINCT FROM true").splitlines():
        if "|" in line:
            bid, alias = line.strip().split("|", 1)
            base_of[alias] = bid

    grants, seen = [], set()
    for line in psql("irlcoop",
                     "SELECT g.id || '|' || g.kind || '|' || gm.sub || '|' || "
                     "array_to_string(gm.roles, ',') FROM group_members gm "
                     "JOIN groups g ON g.id=gm.group_id").splitlines():
        if "|" not in line:
            continue
        gid, kind, sub, roles = line.strip().split("|", 3)
        email = sub_email.get(sub)
        if not email:
            continue  # synthetic sub / no Keycloak user -> can't grant by email
        base_id = base_of.get(schema_of.get(gid))
        if not base_id:
            continue
        role_list = roles.split(",")
        role = "owner" if ("owner" in role_list or "platform-admin" in role_list) else "editor"
        key = (base_id, email)
        if key in seen:
            continue
        seen.add(key)
        grants.append({"base_id": base_id, "email": email, "role": role})

    json.dump(grants, sys.stdout)


if __name__ == "__main__":
    main()
