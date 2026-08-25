# coop-groups-mapper — Keycloak `groups` scope backed by coop-api

Makes Keycloak's `groups` scope **real**: instead of Keycloak's own group model
(which the coop doesn't use), a custom OIDC protocol mapper resolves a user's
**related groups** live from coop-api on every token mint and emits their ids
as the `groups` claim. coop-api stays the source of truth (Path A of the
"Keycloak provides groups" design) — Keycloak fetches on demand.

## Flow

```
Keycloak token mint (scope includes `groups`)
  └─ CoopGroupsMapper.setClaim()
       └─ GET {api_url}?sub=<subject>   (Authorization: Bearer {api_token})
            └─ coop-api /api/internal/groups
                 └─ getRelatedGroups(sub)  (the user's seats, incl. their 1-of-1 group)
                      └─ { "groups": ["<group-uuid>", ...] }
  └─ token.otherClaims["groups"] = ["<group-uuid>", ...]
```

`groups` = the user's **related groups** (the functional group concept, NOT
permissions): their own 1-of-1 group (kind='personal', seated as owner) plus
every coop group they hold a seat in — identified by group id (uuid).

## Files

- `CoopGroupsMapper.java` — the mapper (extends `AbstractOIDCProtocolMapper`,
  implements the OIDC ID/access/userinfo/introspection marker interfaces).
- `META-INF/services/org.keycloak.protocol.ProtocolMapper` — SPI registration
  (lists the mapper class; this is the *only* service file Keycloak 25 reads).
- `build.sh` — rebuilds `../coop-groups-mapper.jar` (needs JDK 21 + the running
  `authentication-keycloak-1` container for the exact 25.0.6 compile classpath).

## Rebuild

```bash
cd infra/instances/dev/assets/keycloak/mapper
JAVA_HOME=/path/to/jdk21 ./build.sh
```

Then `uv run --with pyyaml python infra/build/generator.py dev` and
`docker compose ... up -d --force-recreate keycloak` (the jar is mounted via
`dev.volumes` in keycloak.yaml, so a recreation re-loads it).

## Register (one-time, in the realm DB — survives restarts)

The mapper is registered on the realm's `groups` client scope (optional scope on
the `coop-api` client). Config:
- `api_url`  = `http://172.17.0.1:3001/api/internal/groups`
- `api_token` = the derived `${SECRET:keycloak.groups-token}` (see
  `infra/out/dev/secrets.env` → `KEYCLOAK_GROUPS_TOKEN`)
- include-in-id-token / access-token / userinfo / introspection = true

## Gotchas

- Keycloak warns `KC-SERVICES0047: ... implementing the internal SPI
  protocol-mapper` on startup — **expected and harmless** (custom protocol
  mappers use an internal SPI by design).
- The mapper is best-effort: a coop-api failure logs a warning and omits the
  claim, never blocking token issuance.
- Today the fleet apps authenticate via coop-api (which re-mints its own JWT),
  so this `groups` claim is consumed by *direct* Keycloak clients (the
  forward-looking "one realm" direction), not the current oauth2-proxy gates.
