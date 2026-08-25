// s3-bridge — coop SSO → MinIO console (one seamless login, no MinIO fork).
//
// Runs behind the s3-gate (oauth2-proxy), which enforces coop SSO + the
// platform-admin role and passes the coop JWT as `X-Forwarded-Access-Token`.
// This bridge exchanges that JWT for MinIO STS credentials via
// AssumeRoleWithWebIdentity (the coop JWT's `policy` claim → consoleAdmin),
// then signs the user into the console through MinIO's built-in ?sts= login —
// no second login, no local minioadmin.
//
// Decision matrix per request:
//   1. ?sts=&sts_a=&sts_s= present  → proxy to console (handleSPA issues the session)
//   2. valid console `token` cookie → proxy to console (already logged in)
//   3. otherwise                    → STS exchange → 302 to /?sts=...&sts_a=...&sts_s=...
const http = require("http");
const net = require("net");

const CONSOLE = process.env.CONSOLE_UPSTREAM || "http://minio:9001"; // console
const STS = process.env.MINIO_STS_URL || "http://minio:9000"; // S3 API (STS)
const PUBLIC = process.env.PUBLIC_CONSOLE_URL || "https://s3.irl.coop";
const PORT = Number(process.env.PORT || 4181);

// Exchange a coop JWT for MinIO web-identity credentials (S3 STS API).
function assumeRoleWithWebIdentity(token) {
  return new Promise((resolve, reject) => {
    const qs = new URLSearchParams({
      Action: "AssumeRoleWithWebIdentity",
      Version: "2011-06-15",
      WebIdentityToken: token,
    });
    const url = new URL(STS);
    const req = http.request(
      {
        hostname: url.hostname,
        port: url.port || 80,
        path: "/?" + qs.toString(),
        method: "POST",
      },
      (res) => {
        let data = "";
        res.on("data", (c) => (data += c));
        res.on("end", () => {
          if (res.statusCode !== 200) {
            return reject(
              new Error(`STS HTTP ${res.statusCode}: ${data.slice(0, 400)}`),
            );
          }
          const pick = (name) => {
            const m = data.match(new RegExp(`<${name}>([^<]+)</${name}>`));
            return m ? m[1] : null;
          };
          const accessKey = pick("AccessKeyId");
          const secretKey = pick("SecretAccessKey");
          const sessionToken = pick("SessionToken");
          if (!accessKey || !secretKey || !sessionToken) {
            return reject(new Error(`STS missing creds: ${data.slice(0, 400)}`));
          }
          resolve({ accessKey, secretKey, sessionToken });
        });
      },
    );
    req.on("error", reject);
    req.end();
  });
}

// Reverse-proxy the request to the console (query string + cookies preserved).
function proxy(req, res) {
  const url = new URL(CONSOLE);
  const upstream = http.request(
    {
      hostname: url.hostname,
      port: url.port || 80,
      path: req.url,
      method: req.method,
      headers: { ...req.headers, host: url.host },
    },
    (up) => {
      res.writeHead(up.statusCode || 502, up.headers);
      up.pipe(res);
    },
  );
  upstream.on("error", () => {
    res.writeHead(502, { "Content-Type": "text/plain" });
    res.end("Bad gateway");
  });
  req.pipe(upstream);
}

// Extract a coop JWT from the request: the `coop_session` cookie (primary,
// 30-day expiry) or the X-Forwarded-Access-Token header (fallback, 1-hour).
function coopJwtFromRequest(req) {
  const cookieHeader = req.headers.cookie || "";
  for (const part of cookieHeader.split(";")) {
    const i = part.indexOf("=");
    if (i < 0) continue;
    const name = part.slice(0, i).trim();
    if (name === "coop_session") {
      const val = part.slice(i + 1).trim();
      if (val) return val;
    }
  }
  const h = req.headers["x-forwarded-access-token"];
  return h && h !== "undefined" ? h : null;
}

const server = http.createServer((req, res) => {
  if (req.url === "/healthz" || req.url === "/healthz/") {
    res.writeHead(200, { "Content-Type": "text/plain" });
    return res.end("ok");
  }

  let url;
  try {
    url = new URL(req.url, "http://localhost");
  } catch {
    url = new URL("/", "http://localhost"); // malformed/protocol-relative URL
  }
  const sts = url.searchParams.get("sts");
  const stsA = url.searchParams.get("sts_a");
  const stsS = url.searchParams.get("sts_s");
  const hasConsoleSession = /(?:^|;\s*)token=/.test(req.headers.cookie || "");

  // 1. STS login params → forward to console (its handleSPA issues the session).
  if (sts && stsA && stsS) return proxy(req, res);
  // 2. Already logged into the console → forward.
  if (hasConsoleSession) return proxy(req, res);

  // 3. Otherwise: exchange a coop JWT for STS creds. Prefer the `coop_session`
  // cookie (30-day coop JWT, same `policy` claim, forwarded by the gate) over
  // the X-Forwarded-Access-Token (1-hour OIDC access token, no refresh token).
  const jwt = coopJwtFromRequest(req);
  if (!jwt) {
    res.writeHead(401, { "Content-Type": "text/plain" });
    return res.end("no coop session");
  }
  return assumeRoleWithWebIdentity(jwt)
    .then(({ accessKey, secretKey, sessionToken }) => {
      const redirect =
        `${PUBLIC}/?sts=${encodeURIComponent(sessionToken)}` +
        `&sts_a=${encodeURIComponent(accessKey)}` +
        `&sts_s=${encodeURIComponent(secretKey)}`;
      res.writeHead(302, { Location: redirect });
      res.end();
    })
    .catch((err) => {
      res.writeHead(502, { "Content-Type": "text/plain" });
      res.end(`STS exchange failed: ${err.message}`);
    });
});

server.on("upgrade", (req, socket, head) => {
  // WebSocket (the console's object-browser live socket at /ws/*). The gate
  // already authenticated the handshake; forward it as a raw TCP tunnel —
  // a plain http.request proxy cannot carry the Upgrade/Sec-WebSocket exchange.
  console.log("upgrade:", req.url);
  const url = new URL(CONSOLE);
  const upstream = net.connect(url.port || 80, url.hostname, () => {
    const lines = [`${req.method} ${req.url} HTTP/1.1`];
    // Forward ALL headers unchanged, INCLUDING Host — the console's WebSocket
    // origin check compares the Origin header against the Host header, so the
    // Host must stay s3.<DOMAIN> (the public origin), not minio:9001.
    for (const [k, v] of Object.entries(req.headers)) {
      lines.push(`${k}: ${Array.isArray(v) ? v.join(", ") : v}`);
    }
    upstream.write(lines.join("\r\n") + "\r\n\r\n");
    if (head && head.length) upstream.write(head);
    socket.pipe(upstream);
    upstream.pipe(socket);
    console.log("upgrade: connected to", url.host);
  });
  upstream.on("error", (e) => {
    console.log("upgrade upstream error:", e.message);
    socket.destroy();
  });
  upstream.on("close", () => socket.destroy());
  socket.on("error", (e) => {
    console.log("upgrade socket error:", e.message);
    upstream.destroy();
  });
  socket.on("close", () => upstream.destroy());
});

server.listen(PORT, () =>
  console.log(`s3-bridge listening on :${PORT} (console=${CONSOLE}, sts=${STS})`),
);
