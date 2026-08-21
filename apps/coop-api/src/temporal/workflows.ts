import {
  proxyActivities,
  sleep,
  continueAsNew,
  startChild,
} from "@temporalio/workflow";
import type * as activities from "./activities";
import type { DigestCandidate } from "./activities";
import { renderNotification } from "../render";

const {
  sweepUndelivered,
  markDelivered,
  collectDigestCandidates,
  markDigested,
  userEmail,
  sendDigestEmail,
} = proxyActivities<typeof activities>({
  startToCloseTimeout: "30 seconds",
  retry: { maximumAttempts: 3, initialInterval: "1 second", backoffCoefficient: 2 },
});

// Deliver one event. The retry policy above is the durable-delivery guarantee:
// at-least-once execution + an idempotent activity = effectively exactly-once.
// For now the activity is a stub (stamps delivered_at); the real delivery
// channel (Stalwart/Matrix, group-configurable) slots in behind the same
// signature without touching this workflow.
export async function deliverNotification(eventId: string): Promise<void> {
  await markDelivered(eventId);
}

// The outbox sweep (option A): self-scheduling, no external trigger. Claim a
// batch of undelivered events, fan out one child workflow per event, sleep,
// then continueAsNew to bound history growth. Temporal keeps it alive across
// worker restarts — the Postgres event store is the durable buffer.
export async function deliverySweep(batchSize = 100): Promise<void> {
  let iterations = 0;
  for (;;) {
    const ids = await sweepUndelivered(batchSize);
    for (const id of ids) {
      const handle = await startChild(deliverNotification, {
        workflowId: `deliver-${id}`,
        args: [id],
      });
      await handle.result();
    }
    await sleep("10 seconds");
    if (++iterations >= 100) {
      await continueAsNew<typeof deliverySweep>(batchSize);
    }
  }
}

// --- Digest lane ---
//
// "Unanswered" = an event that was pushed but never read or cleared. The digest
// collects every unanswered event older than a window, groups it by source and
// then by its associated group (mailbox for mail, room for matrix — the
// room→group mapping in resource_scopes replaces these stand-ins), and mails
// one digest per user through Stalwart. Each folded-in event is marked digested
// so a re-run doesn't repeat it.

function count(items: Map<string, DigestCandidate[]>): number {
  let n = 0;
  for (const v of items.values()) n += v.length;
  return n;
}

// Associated-group label (stand-in until resource_scopes): the mailbox for
// mail, the room for matrix, the source as a last resort.
function groupLabel(c: DigestCandidate): string {
  const p = c.payload ?? {};
  if (c.source === "mail") return typeof p.to === "string" ? p.to : "mailbox";
  if (c.source === "matrix") return typeof p.room === "string" ? p.room : "chat";
  return c.source;
}

function sourceTitle(source: string): string {
  if (source === "mail") return "Email";
  if (source === "matrix") return "Matrix";
  return source;
}

function renderDigest(items: DigestCandidate[]): { text: string; html: string } {
  const bySource = new Map<string, Map<string, DigestCandidate[]>>();
  for (const c of items) {
    const src = c.source;
    const lbl = groupLabel(c);
    if (!bySource.has(src)) bySource.set(src, new Map());
    const byGroup = bySource.get(src)!;
    if (!byGroup.has(lbl)) byGroup.set(lbl, []);
    byGroup.get(lbl)!.push(c);
  }

  const lines: string[] = [
    `You have ${items.length} unanswered notification${items.length === 1 ? "" : "s"}.`,
  ];
  const html: string[] = [
    `<p>You have ${items.length} unanswered notification${items.length === 1 ? "" : "s"}.</p>`,
  ];

  for (const [source, groups] of bySource) {
    lines.push("", `${sourceTitle(source)} (${count(groups)})`);
    html.push(`<h3 style="margin:16px 0 4px">${sourceTitle(source)} (${count(groups)})</h3>`);
    for (const [label, cs] of groups) {
      lines.push(`  ${label}`);
      html.push(`<p style="margin:8px 0 0;font-weight:600">${label}</p><ul style="margin:2px 0 0">`);
      for (const c of cs) {
        const n = renderNotification({
          id: c.event_id,
          type: c.type,
          payload: c.payload,
          occurred_at: c.occurred_at,
        });
        lines.push(`    • ${n.title} — ${n.body}`);
        html.push(`<li>${n.title} — ${n.body}</li>`);
      }
      html.push("</ul>");
    }
  }

  return {
    text: lines.join("\n"),
    html: html.join(""),
  };
}

// One-shot digest pass: collect, group, send, mark. Returns counts for
// observability / tests.
export async function digestOnce(olderThan: string): Promise<{ users: number; sent: number }> {
  const candidates = await collectDigestCandidates(olderThan);
  const byUser = new Map<string, DigestCandidate[]>();
  for (const c of candidates) {
    if (!byUser.has(c.user_sub)) byUser.set(c.user_sub, []);
    byUser.get(c.user_sub)!.push(c);
  }

  let sent = 0;
  for (const [sub, items] of byUser) {
    try {
      const email = await userEmail(sub);
      if (!email) {
        // No deliverable address — still mark digested so the next pass doesn't
        // re-collect the same unanswered events forever.
        for (const c of items) await markDigested(sub, c.event_id);
        continue;
      }
      const { text, html } = renderDigest(items);
      const subject = `irl.coop digest: ${items.length} unanswered notification${items.length === 1 ? "" : "s"}`;
      await sendDigestEmail(email, subject, text, html);
      for (const c of items) await markDigested(sub, c.event_id);
      sent += 1;
    } catch (err) {
      // A single user's failure must not sink the whole pass; Temporal's retry
      // policy on the ACTIVITIES above handles transient errors per call. Here
      // we log and move on — the undigested events remain candidates next pass.
      continue;
    }
  }
  return { users: byUser.size, sent };
}

// Self-scheduling digest loop (mirrors deliverySweep): run a pass, sleep the
// interval, continueAsNew to bound history.
export async function digestSweep(olderThan: string, intervalSeconds = 3600): Promise<void> {
  let iterations = 0;
  for (;;) {
    await digestOnce(olderThan);
    await sleep(intervalSeconds);
    if (++iterations >= 100) {
      await continueAsNew<typeof digestSweep>(olderThan, intervalSeconds);
    }
  }
}
