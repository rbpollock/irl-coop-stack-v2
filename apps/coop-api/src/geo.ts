import type { FastifyInstance } from "fastify";
import { verifyBearer } from "./verify-jwt";
import { withIdentity, pool } from "./db";

// Sovereign maps — group-scoped tracks (paths) + markers (points). Every query
// runs inside withIdentity(sub) so Postgres RLS (coop_can_view_group / owner
// checks in coop_rls.sql) scopes it to what the caller may see. Public/federated
// content is served by the anonymous /discover path (no app.sub). Geometry is
// GeoJSON in/out; the coarse `geohash` column is derived server-side from the
// precise shape (the privacy/queryability split — see sovereign-maps-tracks.md).

const VISIBILITY = ["private", "contact", "group", "federated", "public"] as const;
const KIND = ["trail", "route", "tour"] as const;

// slug -> group id, RLS-scoped (only resolves a group the caller may view).
async function resolveGroup(sub: string, slug: string): Promise<string | null> {
  return withIdentity(sub, async (client) => {
    const { rows } = await client.query<{ id: string }>(
      "SELECT id FROM groups WHERE slug = $1",
      [slug],
    );
    return rows[0]?.id ?? null;
  });
}

// GeoJSON object -> PostGIS geometry (SRID 4326), or null.
function geoJsonToText(geom: unknown): string | null {
  return typeof geom === "object" && geom !== null ? JSON.stringify(geom) : null;
}

export default async function geoRoutes(fastify: FastifyInstance): Promise<void> {
  // ---- tracks (paths: trail / route / tour) ----

  fastify.get("/api/v1/groups/:slug/tracks", async (request, reply) => {
    const claims = verifyBearer(request, reply);
    if (!claims) return;
    const slug = (request.params as any).slug;
    const gid = await resolveGroup(claims.sub, slug);
    if (!gid) return reply.code(404).send({ error: "no_group" });

    const rows = await withIdentity(claims.sub, async (client) => {
      const { rows } = await client.query(
        `SELECT id, kind, title, description, category, tags, visibility, review_status,
                ST_AsGeoJSON(geometry)::json AS geometry,
                timestamps, created_at, updated_at
           FROM tracks
          WHERE group_id = $1 AND deleted_at IS NULL
          ORDER BY created_at DESC`,
        [gid],
      );
      return rows;
    });
    return reply.send(rows);
  });

  fastify.post("/api/v1/groups/:slug/tracks", async (request, reply) => {
    const claims = verifyBearer(request, reply);
    if (!claims) return;
    const slug = (request.params as any).slug;
    const body = (request.body ?? {}) as Record<string, any>;
    const gid = await resolveGroup(claims.sub, slug);
    if (!gid) return reply.code(404).send({ error: "no_group" });

    const geom = geoJsonToText(body.geometry);
    if (!geom) return reply.code(400).send({ error: "geometry (GeoJSON) is required" });
    const kind = KIND.includes(body.kind) ? body.kind : "trail";
    const visibility = VISIBILITY.includes(body.visibility) ? body.visibility : "private";

    const row = await withIdentity(claims.sub, async (client) => {
      const { rows } = await client.query(
        `INSERT INTO tracks
           (group_id, owner_id, kind, title, description, category, tags,
            geometry, geohash, timestamps, visibility, review_status)
         VALUES ($1, $2, $3, $4, $5, $6, $7,
                 ST_SetSRID(ST_GeomFromGeoJSON($8), 4326),
                 ST_GeoHash(ST_Centroid(ST_SetSRID(ST_GeomFromGeoJSON($8), 4326)), 5),
                 $9, $10, $11)
         RETURNING id, kind, title, description, category, tags, visibility, review_status,
                   ST_AsGeoJSON(geometry)::json AS geometry, geohash, created_at`,
        [
          gid, claims.sub, kind, body.title ?? null, body.description ?? null,
          body.category ?? null, body.tags ?? [], geom,
          body.timestamps ?? null, visibility, body.review_status ?? "draft",
        ],
      );
      return rows[0];
    });
    return reply.code(201).send(row);
  });

  fastify.get("/api/v1/groups/:slug/tracks/:id", async (request, reply) => {
    const claims = verifyBearer(request, reply);
    if (!claims) return;
    const slug = (request.params as any).slug;
    const id = (request.params as any).id;
    const gid = await resolveGroup(claims.sub, slug);
    if (!gid) return reply.code(404).send({ error: "no_group" });

    const result = await withIdentity(claims.sub, async (client) => {
      const t = await client.query(
        `SELECT id, kind, title, description, category, tags, visibility, review_status,
                ST_AsGeoJSON(geometry)::json AS geometry, geohash, timestamps, created_at, updated_at
           FROM tracks WHERE group_id = $1 AND id = $2 AND deleted_at IS NULL`,
        [gid, id],
      );
      if (t.rows.length === 0) return null;
      const w = await client.query(
        `SELECT id, seq, title, description, media, ST_AsGeoJSON(point)::json AS point, geohash
           FROM waypoints WHERE track_id = $1 AND deleted_at IS NULL ORDER BY seq`,
        [id],
      );
      return { ...t.rows[0], waypoints: w.rows };
    });
    if (!result) return reply.code(404).send({ error: "no_track" });
    return reply.send(result);
  });

  fastify.put("/api/v1/groups/:slug/tracks/:id", async (request, reply) => {
    const claims = verifyBearer(request, reply);
    if (!claims) return;
    const slug = (request.params as any).slug;
    const id = (request.params as any).id;
    const body = (request.body ?? {}) as Record<string, any>;
    const gid = await resolveGroup(claims.sub, slug);
    if (!gid) return reply.code(404).send({ error: "no_group" });

    const sets: string[] = [];
    const vals: any[] = [];
    const push = (col: string, v: any) => { sets.push(`${col} = $${vals.length + 1}`); vals.push(v); };
    if (body.title !== undefined) push("title", body.title ?? null);
    if (body.description !== undefined) push("description", body.description ?? null);
    if (body.category !== undefined) push("category", body.category ?? null);
    if (body.tags !== undefined) push("tags", body.tags ?? []);
    if (VISIBILITY.includes(body.visibility)) push("visibility", body.visibility);
    if (body.review_status !== undefined) push("review_status", body.review_status ?? "draft");
    const geom = geoJsonToText(body.geometry);
    if (geom) {
      sets.push(`geometry = ST_SetSRID(ST_GeomFromGeoJSON($${vals.length + 1}), 4326)`); vals.push(geom);
      sets.push(`geohash = ST_GeoHash(ST_Centroid(ST_SetSRID(ST_GeomFromGeoJSON($${vals.length + 1}), 4326)), 5)`); vals.push(geom);
    }
    if (sets.length === 0) return reply.code(400).send({ error: "nothing to update" });

    const row = await withIdentity(claims.sub, async (client) => {
      // RLS (tracks_update) permits only the owner or a group owner.
      vals.push(id, gid);
      await client.query(
        `UPDATE tracks SET ${sets.join(", ")}, updated_at = now()
          WHERE id = $${vals.length - 1} AND group_id = $${vals.length} AND deleted_at IS NULL`,
        vals,
      );
      const { rows } = await client.query(
        `SELECT id, kind, title, description, category, tags, visibility, review_status,
                ST_AsGeoJSON(geometry)::json AS geometry, geohash, updated_at
           FROM tracks WHERE id = $1 AND deleted_at IS NULL`,
        [id],
      );
      return rows[0] ?? null;
    });
    if (!row) return reply.code(404).send({ error: "no_track" });
    return reply.send(row);
  });

  fastify.delete("/api/v1/groups/:slug/tracks/:id", async (request, reply) => {
    const claims = verifyBearer(request, reply);
    if (!claims) return;
    const slug = (request.params as any).slug;
    const id = (request.params as any).id;
    const gid = await resolveGroup(claims.sub, slug);
    if (!gid) return reply.code(404).send({ error: "no_group" });

    const deleted = await withIdentity(claims.sub, async (client) => {
      const r = await client.query(
        `UPDATE tracks SET deleted_at = now() WHERE id = $1 AND group_id = $2 AND deleted_at IS NULL`,
        [id, gid],
      );
      return (r.rowCount ?? 0) > 0;
    });
    if (!deleted) return reply.code(404).send({ error: "no_track" });
    return reply.code(204).send();
  });

  // ---- markers (points: pins / LBRs) ----

  fastify.get("/api/v1/groups/:slug/markers", async (request, reply) => {
    const claims = verifyBearer(request, reply);
    if (!claims) return;
    const slug = (request.params as any).slug;
    const gid = await resolveGroup(claims.sub, slug);
    if (!gid) return reply.code(404).send({ error: "no_group" });

    const rows = await withIdentity(claims.sub, async (client) => {
      const { rows } = await client.query(
        `SELECT id, source, title, url, category, tags, visibility,
                ST_AsGeoJSON(point)::json AS point, geohash, occurs_at, expires_at, created_at, updated_at
           FROM markers
          WHERE group_id = $1 AND deleted_at IS NULL
          ORDER BY created_at DESC`,
        [gid],
      );
      return rows;
    });
    return reply.send(rows);
  });

  fastify.post("/api/v1/groups/:slug/markers", async (request, reply) => {
    const claims = verifyBearer(request, reply);
    if (!claims) return;
    const slug = (request.params as any).slug;
    const body = (request.body ?? {}) as Record<string, any>;
    const gid = await resolveGroup(claims.sub, slug);
    if (!gid) return reply.code(404).send({ error: "no_group" });

    const point = geoJsonToText(body.point);
    if (!point) return reply.code(400).send({ error: "point (GeoJSON) is required" });
    const visibility = VISIBILITY.includes(body.visibility) ? body.visibility : "private";

    const row = await withIdentity(claims.sub, async (client) => {
      const { rows } = await client.query(
        `INSERT INTO markers
           (group_id, owner_id, source, title, url, category, tags,
            point, geohash, visibility, occurs_at, expires_at)
         VALUES ($1, $2, $3, $4, $5, $6, $7,
                 ST_SetSRID(ST_GeomFromGeoJSON($8), 4326),
                 ST_GeoHash(ST_SetSRID(ST_GeomFromGeoJSON($8), 4326), 5),
                 $9, $10, $11)
         RETURNING id, source, title, url, category, tags, visibility,
                   ST_AsGeoJSON(point)::json AS point, geohash, occurs_at, expires_at, created_at`,
        [
          gid, claims.sub, body.source ?? "pin", body.title ?? null, body.url ?? null,
          body.category ?? null, body.tags ?? [], point,
          visibility, body.occurs_at ?? null, body.expires_at ?? null,
        ],
      );
      return rows[0];
    });
    return reply.code(201).send(row);
  });

  fastify.put("/api/v1/groups/:slug/markers/:id", async (request, reply) => {
    const claims = verifyBearer(request, reply);
    if (!claims) return;
    const slug = (request.params as any).slug;
    const id = (request.params as any).id;
    const body = (request.body ?? {}) as Record<string, any>;
    const gid = await resolveGroup(claims.sub, slug);
    if (!gid) return reply.code(404).send({ error: "no_group" });

    const sets: string[] = [];
    const vals: any[] = [];
    const push = (col: string, v: any) => { sets.push(`${col} = $${vals.length + 1}`); vals.push(v); };
    if (body.title !== undefined) push("title", body.title ?? null);
    if (body.url !== undefined) push("url", body.url ?? null);
    if (body.category !== undefined) push("category", body.category ?? null);
    if (body.tags !== undefined) push("tags", body.tags ?? []);
    if (VISIBILITY.includes(body.visibility)) push("visibility", body.visibility);
    if (body.occurs_at !== undefined) push("occurs_at", body.occurs_at ?? null);
    if (body.expires_at !== undefined) push("expires_at", body.expires_at ?? null);
    const point = geoJsonToText(body.point);
    if (point) {
      sets.push(`point = ST_SetSRID(ST_GeomFromGeoJSON($${vals.length + 1}), 4326)`); vals.push(point);
      sets.push(`geohash = ST_GeoHash(ST_SetSRID(ST_GeomFromGeoJSON($${vals.length + 1}), 4326), 5)`); vals.push(point);
    }
    if (sets.length === 0) return reply.code(400).send({ error: "nothing to update" });

    const row = await withIdentity(claims.sub, async (client) => {
      vals.push(id, gid);
      await client.query(
        `UPDATE markers SET ${sets.join(", ")}, updated_at = now()
          WHERE id = $${vals.length - 1} AND group_id = $${vals.length} AND deleted_at IS NULL`,
        vals,
      );
      const { rows } = await client.query(
        `SELECT id, source, title, url, category, tags, visibility,
                ST_AsGeoJSON(point)::json AS point, geohash, occurs_at, expires_at, updated_at
           FROM markers WHERE id = $1 AND deleted_at IS NULL`,
        [id],
      );
      return rows[0] ?? null;
    });
    if (!row) return reply.code(404).send({ error: "no_marker" });
    return reply.send(row);
  });

  fastify.delete("/api/v1/groups/:slug/markers/:id", async (request, reply) => {
    const claims = verifyBearer(request, reply);
    if (!claims) return;
    const slug = (request.params as any).slug;
    const id = (request.params as any).id;
    const gid = await resolveGroup(claims.sub, slug);
    if (!gid) return reply.code(404).send({ error: "no_group" });

    const deleted = await withIdentity(claims.sub, async (client) => {
      const r = await client.query(
        `UPDATE markers SET deleted_at = now() WHERE id = $1 AND group_id = $2 AND deleted_at IS NULL`,
        [id, gid],
      );
      return (r.rowCount ?? 0) > 0;
    });
    if (!deleted) return reply.code(404).send({ error: "no_marker" });
    return reply.code(204).send();
  });

  // ---- federation discover (explore mode) — anonymous, public content only ----

  fastify.get("/api/v1/discover/map", async (request, reply) => {
    const q = request.query as Record<string, string | undefined>;
    // bbox = "minLng,minLat,maxLng,maxLat"
    const parts = (q.bbox ?? "").split(",").map(Number);
    if (parts.length !== 4 || parts.some(Number.isNaN)) {
      return reply.code(400).send({ error: "bbox=minLng,minLat,maxLng,maxLat required" });
    }
    const [minLng, minLat, maxLng, maxLat] = parts;
    const category = q.category ?? null;
    const params: any[] = [minLng, minLat, maxLng, maxLat];
    let catClause = "";
    if (category) { params.push(category); catClause = `AND category = $${params.length}`; }

    // Anonymous: only public/federated markers + approved public tours. The
    // coarse geohash is not used here — the point/geometry GiST index (built on
    // public/federated rows) answers the bbox intersection.
    const markers = await pool.query(
      `SELECT id, source, title, url, category, tags, ST_AsGeoJSON(point)::json AS point
         FROM markers
        WHERE deleted_at IS NULL AND visibility IN ('public','federated')
          AND point && ST_MakeEnvelope($1, $2, $3, $4, 4326)
          ${catClause}
        ORDER BY created_at DESC
        LIMIT 500`,
      params,
    );
    const tours = await pool.query(
      `SELECT id, kind, title, description, category, tags, ST_AsGeoJSON(geometry)::json AS geometry
         FROM tracks
        WHERE deleted_at IS NULL AND kind = 'tour' AND visibility = 'public' AND review_status = 'approved'
          AND geometry && ST_MakeEnvelope($1, $2, $3, $4, 4326)
          ${catClause}
        ORDER BY created_at DESC
        LIMIT 500`,
      params,
    );
    return reply.send({ markers: markers.rows, tours: tours.rows });
  });
}
