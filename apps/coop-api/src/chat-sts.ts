import { FastifyInstance } from "fastify"

import { verifyBearer } from "./verify-jwt"

// MinIO STS endpoint. coop-api is a host process; MinIO sits on the docker
// gateway (172.17.0.1:9000), same as the docs/files/avatars S3 clients.
const MINIO_STS_URL = process.env.MINIO_STS_URL ?? "http://172.17.0.1:9000"

// Inline session policy scoped to a member's own prefix. MinIO STS intersects
// this with the role policy from the coop JWT's `policy` claim (consoleAdmin for
// storage admins, null for everyone else) — so a regular member's creds touch
// exactly <bucket>/<sub>/*, and an admin's are still pinned to the prefix.
function scopedPolicy(bucket: string, sub: string): string {
  return JSON.stringify({
    Version: "2012-10-17",
    Statement: [
      {
        Effect: "Allow",
        Action: [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket",
          "s3:GetBucketLocation",
        ],
        Resource: [
          `arn:aws:s3:::${bucket}/${sub}`,
          `arn:aws:s3:::${bucket}/${sub}/*`,
        ],
      },
    ],
  })
}

async function mintScopedSts(
  jwt: string,
  bucket: string,
  sub: string,
): Promise<{ accessKey: string; secretKey: string; sessionToken: string }> {
  const qs = new URLSearchParams({
    Action: "AssumeRoleWithWebIdentity",
    Version: "2011-06-15",
    WebIdentityToken: jwt,
    Policy: scopedPolicy(bucket, sub),
  })
  const res = await fetch(`${MINIO_STS_URL}/?${qs.toString()}`, {
    method: "POST",
  })
  if (!res.ok) {
    const txt = await res.text().catch(() => "")
    throw new Error(`STS HTTP ${res.status}: ${txt.slice(0, 300)}`)
  }
  const xml = await res.text()
  const pick = (name: string) =>
    (xml.match(new RegExp(`<${name}>([^<]+)</${name}>`)) || [])[1] ?? null
  const accessKey = pick("AccessKeyId")
  const secretKey = pick("SecretAccessKey")
  const sessionToken = pick("SessionToken")
  if (!accessKey || !secretKey || !sessionToken) {
    throw new Error(`STS missing creds: ${xml.slice(0, 300)}`)
  }
  return { accessKey, secretKey, sessionToken }
}

// Mint scoped MinIO STS credentials for a member's own prefix. The browser uses
// them to read/write <bucket>/<sub>/… directly — delegation, not custody: the
// coop holds no key that can read every member's chat.
export default async function chatStsRoutes(fastify: FastifyInstance) {
  fastify.get("/api/v1/chat/sts", async (request, reply) => {
    const claims = verifyBearer(request, reply)
    if (!claims) return // 401 already sent
    const sub = String((claims as any).sub ?? "")
    if (!sub) return reply.code(400).send({ error: "no sub" })

    const bucket = String((request.query as any)?.bucket ?? "chat")
    if (!/^[a-z0-9][a-z0-9-]{0,62}$/.test(bucket)) {
      return reply.code(400).send({ error: "invalid bucket" })
    }

    const rawJwt = String(request.headers.authorization ?? "").replace(
      /^Bearer\s+/i,
      "",
    )
    try {
      const creds = await mintScopedSts(rawJwt, bucket, sub)
      return reply.send({
        ...creds,
        bucket,
        prefix: `${bucket}/${sub}`,
        endpoint:
          process.env.S3_API_PUBLIC_URL ?? "https://s3api.irl.coop",
        region: "us-east-1",
      })
    } catch (err) {
      request.log.error(
        { err: (err as Error).message },
        "chat sts mint failed",
      )
      return reply.code(502).send({ error: "sts_failed" })
    }
  })
}
