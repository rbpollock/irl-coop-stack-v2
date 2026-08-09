import 'dotenv/config'
import Fastify from 'fastify'
import cors from '@fastify/cors'
import formbody from '@fastify/formbody'
import authRoutes from './auth'
import onboardingRoutes from './onboarding'
import safeRoutes from './safe'
import usernameRoutes from './username'

const fastify = Fastify({
  logger: true,
  trustProxy: true, // Trust proxy headers to correctly get client IP
})

fastify.register(cors, {
  origin: ['http://localhost:3000', 'https://irl.coop', 'https://api.irl.coop'],
  methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
  allowedHeaders: ['Content-Type', 'Authorization'],
  credentials: true, // Allow cookies and authorization headers
})

fastify.register(formbody)
fastify.register(authRoutes)
fastify.register(onboardingRoutes)
fastify.register(safeRoutes)
fastify.register(usernameRoutes)

const start = async () => {
  try {
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
