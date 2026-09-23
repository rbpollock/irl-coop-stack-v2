// Minimal SigV4 S3 client for the browser, using WebCrypto (crypto.subtle).
// Port of coop-api's s3-client.ts signer for STS (temporary) credentials —
// signs the x-amz-security-token header that STS creds require.

export type StsCreds = {
  accessKey: string
  secretKey: string
  sessionToken: string
  bucket: string
  prefix: string // e.g. "chat/{sub}"
  endpoint: string // e.g. "https://s3api.irl.coop"
  region: string
}

async function hmac(key: Uint8Array, data: string): Promise<Uint8Array> {
  const k = await crypto.subtle.importKey(
    "raw",
    key as unknown as BufferSource,
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"]
  )
  const sig = await crypto.subtle.sign(
    "HMAC",
    k,
    new TextEncoder().encode(data)
  )
  return new Uint8Array(sig)
}

async function sha256Hex(data: string): Promise<string> {
  const digest = await crypto.subtle.digest(
    "SHA-256",
    new TextEncoder().encode(data)
  )
  return [...new Uint8Array(digest)]
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("")
}

// Sign + send one S3 request (path-style: /{bucket}/{objectKey}).
async function sigv4Request(
  creds: StsCreds,
  method: string,
  objectKey: string, // e.g. "chat/{sub}/abc.json" (bucket included)
  query = "",
  body?: string
): Promise<Response> {
  const path = `/${objectKey}`
  const now = new Date()
  const amz = now.toISOString().replace(/[:-]|\.\d{3}/g, "")
  const date = amz.slice(0, 8)
  const payloadHash = await sha256Hex(body ?? "")

  const headers: Record<string, string> = {
    host: new URL(creds.endpoint).host,
    "x-amz-content-sha256": payloadHash,
    "x-amz-date": amz,
    "x-amz-security-token": creds.sessionToken,
  }
  const signedHeaders = Object.keys(headers).sort().join(";")
  const canonicalQuery = query.replace(/^[?]/, "")
  const canonical =
    `${method}\n${path}\n${canonicalQuery}\n` +
    Object.keys(headers)
      .sort()
      .map((k) => `${k}:${headers[k]}\n`)
      .join("") +
    `\n${signedHeaders}\n${payloadHash}`

  const scope = `${date}/${creds.region}/s3/aws4_request`
  const stringToSign = `AWS4-HMAC-SHA256\n${amz}\n${scope}\n${await sha256Hex(canonical)}`

  const kDate = await hmac(
    new TextEncoder().encode(`AWS4${creds.secretKey}`),
    date
  )
  const kRegion = await hmac(kDate, creds.region)
  const kService = await hmac(kRegion, "s3")
  const kSigning = await hmac(kService, "aws4_request")
  const signature = [...(await hmac(kSigning, stringToSign))]
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("")

  headers.authorization =
    `AWS4-HMAC-SHA256 Credential=${creds.accessKey}/${scope}, ` +
    `SignedHeaders=${signedHeaders}, Signature=${signature}`

  return fetch(`${creds.endpoint}/${objectKey}${query}`, {
    method,
    headers,
    body: body ?? undefined,
  })
}

export function getObject(
  creds: StsCreds,
  objectKey: string
): Promise<Response> {
  return sigv4Request(creds, "GET", objectKey)
}

export function putObject(
  creds: StsCreds,
  objectKey: string,
  body: string
): Promise<Response> {
  return sigv4Request(creds, "PUT", objectKey, "", body)
}

// LIST objects under a prefix, returning {key, lastModified} in order.
export async function listObjects(
  creds: StsCreds,
  prefix: string
): Promise<{ key: string; lastModified: string }[]> {
  const q = `?list-type=2&prefix=${encodeURIComponent(prefix)}`
  const res = await sigv4Request(creds, "GET", creds.bucket, q)
  if (!res.ok) return []
  const xml = await res.text()
  const out: { key: string; lastModified: string }[] = []
  for (const c of xml.match(/<Contents>[\s\S]*?<\/Contents>/g) ?? []) {
    const key = (c.match(/<Key>([^<]+)<\/Key>/) || [])[1]
    const lastModified =
      (c.match(/<LastModified>([^<]+)<\/LastModified>/) || [])[1] ?? ""
    if (key) out.push({ key, lastModified })
  }
  return out
}
