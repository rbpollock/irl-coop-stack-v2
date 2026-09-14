import * as crypto from "node:crypto";
import type { FastifyInstance } from "fastify";
import { Pool } from "pg";
import { verifyBearer } from "./verify-jwt";
import { withIdentity, provisionTelephonyResource, pool } from "./db";

// Telephony surface — the dashboard "Calls" app is the consumer. This module
// is the identity seam: the caller's coop JWT (sub) resolves to a SIP identity
// and the browserphone registers over WSS against FreeSWITCH. See
// docs/design/telephony.md ("Extension identity — every group is a phone" and
// "Browserphone integration seam").
//
// Resolution:
//   sub → own group (groups.kind='personal', created_by=sub)
//       → telephony_resources (group_id=own group, resource_type='extension')
//       → external_ref (fusionpbx v_extensions.extension = SIP username)
//   + SIP digest secret from FusionPBX v_extensions.password (TODO(vault): the
//     user Vault becomes the source of truth; v_extensions is the enforcement
//     copy — read the Vault instead once it lands).
//   + caller-ID name from the coop JWT profile.
//
// The Vault is not built yet, so the SIP secret is read from FusionPBX's own
// store (v_extensions.password) — that is FusionPBX's authoritative digest
// secret, NOT a coop projection, so it is safe to read here.

// FusionPBX DB — read-only pool for the SIP digest secret. FusionPBX's own
// system database (database.0) already lives on the shared Citus.
const fusionpbxPool = new Pool({
  host: process.env.FUSIONPBX_DB_HOST ?? "172.17.0.1",
  port: Number(process.env.FUSIONPBX_DB_PORT ?? 5432),
  user: process.env.FUSIONPBX_DB_USER ?? "fusionpbx",
  password: process.env.FUSIONPBX_DB_PASSWORD ?? "",
  database: process.env.FUSIONPBX_DB_NAME ?? "fusionpbx",
  max: 3,
});

type SipConfig = {
  server: string; // WSS host (WebSocket endpoint) — "sip.irl.coop" (wildcard cert)
  domain: string; // SIP domain (SIP URI @domain) — "irl.coop"
  extension: string;
  profileUserID: string; // stable identity (Keycloak sub) — seeds the phone's local profile
  password: string;
  fullname: string | null;
  avatar: string | null; // custom avatar URL (else the DiceBear default from profileUserID)
  wss: { port: string; path: string };
};

async function resolveMemberConfig(claims: any): Promise<SipConfig | null> {
  const sub = claims?.sub as string | undefined;
  if (!sub) return null;

  // sub → own group → extension resource → SIP username. groups and
  // telephony_resources are FORCE RLS (scoped by app.sub), so this runs
  // inside withIdentity.
  const extension = await withIdentity<string | null>(sub, async (client) => {
    const { rows } = await client.query(
      `SELECT tr.external_ref AS extension
         FROM telephony_resources tr
         JOIN groups g ON g.id = tr.group_id
        WHERE g.created_by = $1
          AND g.kind = 'personal'
          AND tr.resource_type = 'extension'
        LIMIT 1`,
      [sub],
    );
    return rows.length === 0 ? null : (rows[0].extension as string);
  });
  if (!extension) return null;

  // SIP digest secret from FusionPBX (TODO(vault): switch to the user Vault).
  const { rows: ext } = await fusionpbxPool.query(
    `SELECT password FROM v_extensions WHERE extension = $1 LIMIT 1`,
    [extension],
  );
  if (ext.length === 0) return null;

  return {
    server: process.env.SIP_WSS_HOST ?? "sip.irl.coop",
    domain: process.env.SIP_DOMAIN ?? "irl.coop",
    extension,
    profileUserID: sub,
    password: ext[0].password,
    fullname: claims.name ?? claims.preferred_username ?? claims.email ?? null,
    avatar: claims.avatar ?? null,
    wss: { port: "7443", path: "/wss" },
  };
}

// The coop's FusionPBX domain (one domain = the coop). Resolved at runtime so
// the extension lands in the right domain regardless of SIP_DOMAIN drift.
async function fusionpbxDomainUuid(): Promise<string | null> {
  const { rows } = await fusionpbxPool.query(
    "SELECT domain_uuid FROM v_domains WHERE domain_name = $1 LIMIT 1",
    [process.env.SIP_DOMAIN ?? "irl.coop"],
  );
  return rows.length ? rows[0].domain_uuid : null;
}

// Convergent personal-telephony provisioning — the write half of the identity
// seam (the read half is resolveMemberConfig above). Called from sign-in so a
// new member gets their own extension automatically, exactly like the manual
// spike (v_extensions row + telephony_resources extension row). Idempotent: a
// second run returns the existing extension unchanged.
export async function ensurePersonalTelephony(sub: string): Promise<string | null> {
  try {
    const existing = await withIdentity<{ groupId: string; ext: string | null } | null>(
      sub,
      async (client) => {
        await client.query("SELECT coop_ensure_personal_group()");
        const r = await client.query(
          `SELECT g.id AS "groupId",
                  (SELECT tr.external_ref FROM telephony_resources tr
                    WHERE tr.group_id = g.id AND tr.resource_type = 'extension' LIMIT 1) AS ext
             FROM groups g
            WHERE g.kind = 'personal' AND g.created_by = $1
            LIMIT 1`,
          [sub],
        );
        return r.rows[0] ?? null;
      },
    );
    if (!existing) return null;
    if (existing.ext) return existing.ext;

    const domainUuid = await fusionpbxDomainUuid();
    if (!domainUuid) return null;

    // Allocate the next numeric extension (the spike used 200–203).
    const { rows } = await fusionpbxPool.query(
      `SELECT COALESCE(MAX(extension::int), 200) + 1 AS next
         FROM v_extensions
        WHERE domain_uuid = $1 AND extension ~ '^[0-9]+$'`,
      [domainUuid],
    );
    const ext = String(rows[0].next);

    // SIP digest secret — raw (the browserphone computes the digest client-side;
    // the Vault is not built yet, so this is the source of truth for now).
    const password = crypto.randomBytes(16).toString("hex");

    // Concrete object in FusionPBX (idempotent).
    await fusionpbxPool.query(
      `INSERT INTO v_extensions (extension_uuid, domain_uuid, extension, number_alias, password, user_context, enabled)
       SELECT gen_random_uuid(), $1, $2, $2, $3, 'default', true
        WHERE NOT EXISTS (SELECT 1 FROM v_extensions WHERE extension = $2 AND domain_uuid = $1)`,
      [domainUuid, ext, password],
    );

    // Projection bridge (system write, coop_ops) — the resource + its scope.
    await provisionTelephonyResource(existing.groupId, "extension", ext, {});

    return ext;
  } catch (err) {
    console.error(
      `[telephony] ensurePersonalTelephony failed for ${sub.slice(0, 8)}: ${(err as Error).message}`,
    );
    return null;
  }
}

export default async function telephonyRoutes(fastify: FastifyInstance): Promise<void> {
  // MGCP phone directory — served to FreeSWITCH's mod_xml_curl directory gateway
  // so ShoreTel/MGCP phones resolve their extension from the coop DB (MAC →
  // extension, from the resource's config.mgcp_mac) instead of hand-edited
  // directory XML. Unauthenticated (FreeSWITCH calls it, not a user); the
  // SECURITY DEFINER coop_mgcp_directory() reads across every member's RLS.
  fastify.post("/api/v1/telephony/mgcp-directory", async (request, reply) => {
    const { rows } = await pool.query<{ extension: string; mac: string }>(
      "SELECT extension, mac FROM coop_mgcp_directory()",
    );

    const users = rows
      .map(
        (r) =>
          `        <user id="${r.extension}">\n` +
          `          <variables>\n` +
          `            <variable name="mgcp_mac" value="${r.mac}"/>\n` +
          `            <variable name="user_context" value="default"/>\n` +
          `          </variables>\n` +
          `        </user>`,
      )
      .join("\n");

    const xml =
      `<?xml version="1.0" encoding="UTF-8"?>\n` +
      `<document type="freeswitch/xml">\n` +
      `  <section name="directory">\n` +
      `    <domain name="${process.env.SIP_DOMAIN ?? "irl.coop"}">\n` +
      `      <groups>\n` +
      `        <group name="default">\n` +
      `          <users>\n` +
      `${users}\n` +
      `          </users>\n` +
      `        </group>\n` +
      `      </groups>\n` +
      `    </domain>\n` +
      `  </section>\n` +
      `</document>`;

    reply.header("Content-Type", "application/xml");
    return reply.send(xml);
  });

  // The browserphone's config: SIP identity for the authenticated member's own
  // device. Same-origin dashboard calls this with the NextAuth access token;
  // the SIP secret is returned to the device only (never in a URL/log).
  fastify.get("/api/v1/telephony/sip-config", async (request, reply) => {
    const claims = verifyBearer(request, reply);
    if (!claims) return;

    try {
      const config = await resolveMemberConfig(claims);
      if (!config) {
        return reply.code(503).send({
          error: "telephony_not_provisioned",
          error_description:
            "No telephony extension provisioned for this member yet.",
        });
      }
      return reply.send(config);
    } catch (err) {
      request.log.error({ err }, "telephony sip-config resolution failed");
      return reply.code(503).send({
        error: "telephony_unavailable",
        error_description: "Telephony backend is unavailable right now.",
      });
    }
  });
}
