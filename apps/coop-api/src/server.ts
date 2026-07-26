import Fastify from 'fastify';
import dotenv from 'dotenv';

dotenv.config();

const fastify = Fastify({ logger: true });

// Basic Health Check
fastify.get('/health', async () => {
  return { status: 'ok' };
});

// Mock Auth-to-Identity Route
// In production, this validates Keycloak JWTs
fastify.post('/auth/verify', async (request, reply) => {
  const authHeader = request.headers.authorization;
  if (!authHeader) {
    return reply.status(401).send({ error: 'Unauthorized' });
  }

  // TODO: Validate JWT via Keycloak Jwks endpoint
  return {
    identity: 'robbie@irl.coop',
    safeAddress: '0x1234567890abcdef1234567890abcdef12345678',
    status: 'authenticated'
  };
});

const start = async () => {
  try {
    await fastify.listen({ port: 3000, host: '0.0.0.0' });
  } catch (err) {
    fastify.log.error(err);
    process.exit(1);
  }
};

start();
