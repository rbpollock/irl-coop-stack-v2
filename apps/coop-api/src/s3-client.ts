import * as crypto from "node:crypto";

// --- Minimal SigV4 S3 client (no AWS SDK in the tree).
// Shared by docs.ts (OnlyOffice store) and files.ts (unified file panel).
// The coop JWT is the SSO boundary; MinIO creds never reach the browser.

export interface S3ClientOpts {
  endpoint: string;
  accessKey: string;
  secretKey: string;
}

function hmac(key: Buffer, data: string): Buffer {
  return crypto.createHmac("sha256", key).update(data).digest();
}

function sha256(data: string | Buffer): string {
  return crypto.createHash("sha256").update(data).digest("hex");
}

export function makeS3Client(opts: S3ClientOpts) {
  const scheme = opts.endpoint.startsWith("localhost") || opts.endpoint.startsWith("172.") ? "http" : "https";

  function sign(method: string, path: string, query = "", body?: Buffer | string): Record<string, string> {
    const now = new Date();
    const amz = now.toISOString().replace(/[:-]|\.\d{3}/g, "");
    const date = amz.slice(0, 8);
    // Hash the RAW bytes — stringifying binary payloads corrupts the hash
    // and MinIO rejects the signature (502 on every PUT).
    const payloadHash = body ? sha256(body as any) : sha256("");
    const headers: Record<string, string> = {
      host: opts.endpoint,
      "x-amz-content-sha256": payloadHash,
      "x-amz-date": amz,
    };
    const signed = Object.keys(headers).sort().join(";");
    const canonicalQuery = query.replace(/^[?]/, "");
    const canonical =
      `${method}\n${path}\n${canonicalQuery}\n` +
      Object.keys(headers).sort().map((k) => `${k}:${headers[k]}\n`).join("") +
      `\n${signed}\n${payloadHash}`;
    const scope = `${date}/us-east-1/s3/aws4_request`;
    const stringToSign = `AWS4-HMAC-SHA256\n${amz}\n${scope}\n${sha256(canonical)}`;
    const kDate = hmac(Buffer.from(`AWS4${opts.secretKey}`), date);
    const kRegion = hmac(kDate, "us-east-1");
    const kService = hmac(kRegion, "s3");
    const kSigning = hmac(kService, "aws4_request");
    const signature = crypto.createHmac("sha256", kSigning).update(stringToSign).digest("hex");
    headers.authorization =
      `AWS4-HMAC-SHA256 Credential=${opts.accessKey}/${scope}, SignedHeaders=${signed}, Signature=${signature}`;
    return headers;
  }

  async function request(
    method: string,
    path: string,
    query = "",
    body?: Buffer,
    extraHeaders?: Record<string, string>
  ): Promise<Response> {
    const hdrs = sign(method, path, query, body);
    const url = `${scheme}://${opts.endpoint}${path}${query}`;
    const resp = await fetch(url, {
      method,
      headers: { ...hdrs, ...(extraHeaders ?? {}) } as any,
      body: body ? new Uint8Array(body) : undefined,
    });
    if (!resp.ok) {
      const txt = await resp.text().catch(() => "");
      console.error(`[s3] ${method} ${url} -> ${resp.status}: ${txt.slice(0, 300)}`);
    }
    return resp;
  }

  return {
    getObject(bucket: string, key: string): Promise<Response> {
      return request("GET", `/${bucket}/${encodeKey(key)}`);
    },
    putObject(bucket: string, key: string, body: Buffer): Promise<Response> {
      return request("PUT", `/${bucket}/${encodeKey(key)}`, "", body, {
        "content-type": "application/octet-stream",
      });
    },
    deleteObject(bucket: string, key: string): Promise<Response> {
      return request("DELETE", `/${bucket}/${encodeKey(key)}`);
    },
    /** List keys under a prefix. Returns the raw XML (caller parses). */
    list(bucket: string, prefix: string): Promise<Response> {
      const q = `?list-type=2&prefix=${encodeURIComponent(prefix)}`;
      return request("GET", `/${bucket}`, q);
    },
    /** Raw request (share-token streaming, etc.). */
    raw(method: string, path: string, query = "", body?: Buffer): Promise<Response> {
      return request(method, path, query, body);
    },
  };
}

function encodeKey(key: string): string {
  // S3 keys may contain chars that need escaping in the path; MinIO accepts
  // the raw key for the common case (alnum, dash, dot, underscore, slash).
  return key.split("/").map((seg) => encodeURIComponent(seg)).join("/");
}

export type S3Client = ReturnType<typeof makeS3Client>;
