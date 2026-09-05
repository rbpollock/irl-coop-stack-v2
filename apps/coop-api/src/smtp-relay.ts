// SMTP relay: accepts mail from internal apps (standard SMTP LOGIN with a shared
// secret) and relays it via Stalwart XOAUTH2 using the coop mailer.
//
// Why: Stalwart (OSS) routes ALL auth through its single OIDC directory, which
// only accepts XOAUTH2 (the coop JWT) — there is no password-auth path. Apps
// like Formbricks that only speak standard SMTP LOGIN (nodemailer
// auth:{type:"LOGIN",user,pass}) cannot reach Stalwart directly. This relay is
// the "coop-api SMTP passthrough": an app points its SMTP at SMTP_RELAY_PORT
// (172.17.0.1:1025) with the shared relay credentials, and mail is delivered
// via the existing XOAUTH2 mailer as notifications@irl.coop.
import { SMTPServer } from "smtp-server";
import { simpleParser } from "mailparser";

import { sendMail } from "./mailer";

const PORT = Number(process.env.SMTP_RELAY_PORT ?? 1025);
const HOST = process.env.SMTP_RELAY_HOST ?? "0.0.0.0";
const USER = process.env.SMTP_RELAY_USER ?? "relay";
// Derived secret lands in secrets.env under its canonical name (SMTP_RELAY,
// from ${SECRET:smtp.relay}); SMTP_RELAY_PASSWORD is the hand-set .env override
// (same pattern as db.ts's COOP_DB_PASSWORD ?? POSTGRES_COOP).
const PASSWORD = process.env.SMTP_RELAY_PASSWORD ?? process.env.SMTP_RELAY ?? "";

export function startSmtpRelay(): void {
  if (!PASSWORD) {
    console.warn("[smtp-relay] SMTP_RELAY_PASSWORD unset — SMTP relay disabled");
    return;
  }

  const server = new SMTPServer({
    authOptional: false,
    // Plain SMTP relay on the internal network — no STARTTLS (Formbricks speaks
    // plain SMTP; without this, smtp-server rejects AUTH with
    // "538 Must issue a STARTTLS command first").
    hideSTARTTLS: true,
    size: 20 * 1024 * 1024,
    onAuth(auth, _session, callback) {
      if (auth.username === USER && auth.password === PASSWORD) {
        return callback(null, { user: USER });
      }
      return callback(new Error("invalid credentials"));
    },
    onData(stream, session, callback) {
      simpleParser(stream)
        .then(async (parsed) => {
          const rcpt = parsed.to?.value?.map((a) => a.address).filter(Boolean) ?? [];
          const to = rcpt.join(", ") || session.envelope.rcptTo.map((a) => a.address).join(", ");
          if (!to) {
            throw new Error("no recipient");
          }
          await sendMail({
            to,
            subject: parsed.subject ?? "(no subject)",
            text: parsed.text ?? "",
            html: parsed.html ?? undefined,
          });
          callback();
        })
        .catch((err: unknown) => {
          const msg = err instanceof Error ? err.message : String(err);
          console.error("[smtp-relay] relay failed:", msg);
          callback(err instanceof Error ? err : new Error(msg));
        });
    },
  });

  server.on("error", (err) => console.error("[smtp-relay] server error:", err));
  server.listen(PORT, HOST, () => console.log(`[smtp-relay] listening on ${HOST}:${PORT}`));
}
