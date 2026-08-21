import * as nodemailer from "nodemailer";

// Digest/notification mail delivery over Stalwart submission (587) with
// XOAUTH2. The sender is the system account `notifications@irl.coop`; its
// coop JWT comes from coop-api's own OIDC password grant (the same issuer
// Stalwart's directory trusts), so no stored SMTP password — the derived
// KEYCLOAK_NOTIFICATIONS is the login credential and never appears in a
// message. This is the "send through Stalwart" primitive the digest workflow
// (and any future group-configurable delivery) calls.

const SMTP_HOST = process.env.SMTP_HOST ?? "127.0.0.1";
const SMTP_PORT = Number(process.env.SMTP_PORT ?? 587);
const SENDER_EMAIL = process.env.DIGEST_FROM ?? "notifications@irl.coop";
const SENDER_PASSWORD = process.env.KEYCLOAK_NOTIFICATIONS ?? "";
const COOP_API_URL = process.env.COOP_API_BASE_URL ?? "http://127.0.0.1:3001";

let cachedToken: { token: string; expiresAt: number } | null = null;

async function senderToken(): Promise<string> {
  if (cachedToken && cachedToken.expiresAt > Date.now() + 60_000) {
    return cachedToken.token;
  }
  const resp = await fetch(`${COOP_API_URL}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username: SENDER_EMAIL, password: SENDER_PASSWORD }),
  });
  if (!resp.ok) throw new Error(`digest sender login failed: ${resp.status}`);
  const data = (await resp.json()) as { access_token?: string; expires_in?: number };
  if (!data.access_token) throw new Error("digest sender login returned no token");
  cachedToken = {
    token: data.access_token,
    expiresAt: Date.now() + (data.expires_in ?? 300) * 1000,
  };
  return cachedToken.token;
}

export type MailMessage = {
  to: string;
  subject: string;
  text: string;
  html?: string;
};

export async function sendMail(msg: MailMessage): Promise<void> {
  const token = await senderToken();
  const transporter = nodemailer.createTransport({
    host: SMTP_HOST,
    port: SMTP_PORT,
    secure: false, // STARTTLS on 587
    requireTLS: true,
    // Internal dev SMTP: Stalwart serves a self-signed cert. Skip verification
    // here (localhost hop) — production behind Traefik would verify normally.
    tls: { rejectUnauthorized: false },
    auth: {
      type: "OAuth2",
      user: SENDER_EMAIL,
      accessToken: token,
    },
  });
  await transporter.sendMail({
    from: `irl.coop notifications <${SENDER_EMAIL}>`,
    to: msg.to,
    subject: msg.subject,
    text: msg.text,
    html: msg.html,
  });
}
