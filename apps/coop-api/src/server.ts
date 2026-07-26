import Fastify from 'fastify';
import dotenv from 'dotenv';
import jwt from 'jsonwebtoken';
import jwksClient from 'jwks-rsa';
import { promisify } from 'util';

dotenv.config();

const fastify = Fastify({ logger: true });

// Basic Health Check
fastify.get('/health', async () => {
  return { status: 'ok' };
});

const client = jwksClient({
  jwksUri: `${process.env.KEYCLOAK_URL}/realms/${process.env.KEYCLOAK_REALM}/protocol/openid-connect/certs`
});

const getSigningKey = promisify(client.getSigningKey);

fastify.post('/auth/verify', async (request, reply) => {
  const authHeader = request.headers.authorization;
  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    return reply.status(401).send({ error: 'Unauthorized' });
  }

  const token = authHeader.split(' ')[1];
  
  try {
    const decoded = jwt.decode(token, { complete: true });
    if (!decoded || typeof decoded === 'string' || !decoded.header.kid) {
        throw new Error('Invalid token structure');
    }
    const kid = (decoded as jwt.Jwt).header.kid!;
    const key = await getSigningKey(kid);
    if (!key || typeof key === 'string') throw new Error('Signing key not found');
    const publicKey = key.getPublicKey();
    
    jwt.verify(token, publicKey, { algorithms: ['RS256'] });

    return {
      identity: 'robbie@irl.coop', // Extract from decoded.payload.preferred_username
      status: 'authenticated'
    };
  } catch (err) {
    return reply.status(401).send({ error: 'Invalid Token' });
  }
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
