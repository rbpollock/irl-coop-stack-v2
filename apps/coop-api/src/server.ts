import * as dotenv from 'dotenv'
import * as path from 'node:path'
import Fastify from 'fastify'

// .env first (hand-maintained local overrides), then the generator-emitted
// derived secrets (declarative source of truth — coop-api is a host process,
// so it sources out/<instance>/secrets.env itself, matching the coop-api.yaml
// comment). dotenv.config() never overrides an already-set var, so .env wins
// on collisions and secrets.env fills the gaps (e.g. POSTGRES_COOP).
dotenv.config()
dotenv.config({ path: path.resolve(process.cwd(), '../../infra/out/dev/secrets.env') })
import cors from '@fastify/cors'
import cookie from '@fastify/cookie'
import formbody from '@fastify/formbody'
import multipart from '@fastify/multipart'
import authRoutes from './auth'
import onboardingRoutes from './onboarding'
import safeRoutes from './safe'
import groupRoutes from './groups'
import { initDb } from './db'
import usernameRoutes from './username'
import docsRoutes from './docs'
import filesRoutes from './files'
import statusRoutes from './status'

const fastify = Fastify({
  logger: true,
  trustProxy: true, // Trust proxy headers to correctly get client IP
  // Share tokens ride the URL path (variant-B: /api/v1/files/s/<token>);
  // Fastify's default 100-char param cap would 414 them.
  maxParamLength: 512,
})

fastify.register(cors, {
  origin: ['http://localhost:3000', 'https://irl.coop', 'https://api.irl.coop'],
  methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
  allowedHeaders: ['Content-Type', 'Authorization'],
  credentials: true, // Allow cookies and authorization headers
})

fastify.register(formbody)
fastify.register(cookie)
// Multipart uploads (the FileManager's fileUploadConfig sends FormData).
// @fastify/multipart v9's FastifyInstance augmentation expects the default
// type provider; this build resolves a generic one, so register()'s overload
// rejects it. Cast is the standard workaround — runtime registration is fine.
fastify.register(multipart as any)
// Raw binary uploads (docs PUT) — Fastify has no octet-stream parser by default.
fastify.addContentTypeParser("application/octet-stream", (request, payload, done) => {
  const chunks: Buffer[] = []
  payload.on("data", (c: Buffer) => chunks.push(c))
  payload.on("end", () => done(null, Buffer.concat(chunks)))
})
fastify.register(authRoutes)
fastify.register(onboardingRoutes)
fastify.register(safeRoutes)
fastify.register(groupRoutes)
fastify.register(usernameRoutes)
fastify.register(docsRoutes)
fastify.register(filesRoutes)
fastify.register(statusRoutes)

const start = async () => {
  try {
    // Self-provision the group projection schema (non-fatal: the auth/status
    // surface stays up even if the store is momentarily unreachable).
    try {
      await initDb()
      fastify.log.info(`group store ready @ ${process.env.COOP_DB_HOST ?? '172.17.0.1'}/${process.env.COOP_DB_NAME ?? 'irlcoop'}`)
    } catch (err) {
      fastify.log.error({ err: (err as Error).message }, 'group store init failed — group endpoints will 500 until the DB is reachable')
    }
    // Listen on all network interfaces (0.0.0.0) so localhost fetches work
    await fastify.listen({ port: Number(process.env.PORT ?? 3001), host: '0.0.0.0' })
    const issuer = process.env.KEYCLOAK_ISSUER ?? 'http://localhost:8081/realms/irl-coop'
    const base = process.env.COOP_API_BASE_URL ?? 'http://localhost:3001'
    fastify.log.info('--- auth bridge chain (redirect-URI matrix) ---')
    fastify.log.info(`NextAuth callback : http://localhost:3000/api/auth/callback/coop-api`)
    fastify.log.info(`coop-api authorize: ${base}/api/auth/authorize`)
    fastify.log.info(`coop-api callback : ${base}/api/auth/keycloak/callback`)
    fastify.log.info(`Keycloak auth     : ${issuer}/protocol/openid-connect/auth`)
    fastify.log.info(`Google broker     : ${issuer}/broker/google/endpoint (must be in Google Cloud Console authorized URIs)`)
    fastify.log.info(`Safe factory      : ${process.env.SAFE_PROXY_FACTORY_ADDRESS ?? '(unset)'} / singleton ${process.env.SAFE_SINGLETON_ADDRESS ?? '(unset)'} @ ${process.env.RPC_URL ?? 'http://127.0.0.1:8545'}`)
  } catch (err) {
    console.error(err)
    process.exit(1)
  }
}
start()
