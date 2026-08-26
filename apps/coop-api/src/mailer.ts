import * as nodemailer from "nodemailer";
import { mintCoopJwt } from "./auth";

// Mail delivery over Stalwart submission (587) with XOAUTH2 — the coop JWT is
// the credential, so there's no stored SMTP password. Two senders:
//
//   - sendMail(): the system account `notifications@irl.coop` (password-grant
//     login → coop JWT) — the digest/notification path.
//   - sendMailAs(): mint a coop JWT for an arbitrary coop identity and send
//     FROM that identity's address — the "on behalf of" utility for
//     group-aware mail. FROM = the user's canonical @irl.coop email or a
//     group's address ({groupname}@irl.coop today; {groupname}.irl.coop
//     subdomain addressing is the group-domain follow-on).
//
// Stalwart's OIDC directory validates the JWT (issuer api.irl.coop, audience
// irl-coop, scope openid+email) and resolves the account via the `email`
// claim — so the JWT must carry the identity's canonical email. The account
// self-provisions on first auth; a never-authed address is rejected.

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

function transporterFor(user: string, token: string): nodemailer.Transporter {
  return nodemailer.createTransport({
    host: SMTP_HOST,
    port: SMTP_PORT,
    secure: false, // STARTTLS on 587
    requireTLS: true,
    // Internal dev SMTP: Stalwart serves a self-signed cert. Skip verification
    // here (localhost hop) — production behind Traefik would verify normally.
    tls: { rejectUnauthorized: false },
    auth: {
      type: "OAuth2",
      user,
      accessToken: token,
    },
  });
}

export async function sendMail(msg: MailMessage): Promise<void> {
  const token = await senderToken();
  await transporterFor(SENDER_EMAIL, token).sendMail({
    from: `irl.coop notifications <${SENDER_EMAIL}>`,
    to: msg.to,
    subject: msg.subject,
    text: msg.text,
    html: msg.html,
  });
}

// A coop identity to send on behalf of. `sub` is the coop subject (a user's
// Keycloak sub, or a group id once groups carry one); `email` is the canonical
// address Stalwart resolves (user: <username>@irl.coop).
export type MailIdentity = { email: string; sub: string };

export async function sendMailAs(from: MailIdentity, msg: MailMessage): Promise<void> {
  const token = await mintCoopJwt({ sub: from.sub }, { email: from.email }, "5m");
  await transporterFor(from.email, token).sendMail({
    from: from.email,
    to: msg.to,
    subject: msg.subject,
    text: msg.text,
    html: msg.html,
  });
}
