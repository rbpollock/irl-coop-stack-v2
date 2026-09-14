import * as path from "node:path";
import * as dotenv from "dotenv";
dotenv.config();
dotenv.config({ path: path.resolve(process.cwd(), "../../infra/out/dev/secrets.env") });

import { NativeConnection, Worker } from "@temporalio/worker";
import { Client, WorkflowNotFoundError } from "@temporalio/client";
import * as activities from "./activities";

// The delivery worker — the durable lane of the event bus (option A). Runs as a
// host process like coop-api, sharing its Postgres access (the activities use
// the same pool). Connects to Temporal at TEMPORAL_ADDRESS (default
// localhost:7233 — published to the host by the temporal pillar).
const ADDRESS = process.env.TEMPORAL_ADDRESS ?? "localhost:7233";
const NAMESPACE = process.env.TEMPORAL_NAMESPACE ?? "coop";
const TASK_QUEUE = process.env.TEMPORAL_TASK_QUEUE ?? "coop-delivery";

// Ensure a self-scheduling sweep exists, WITHOUT resurrecting one the operator
// deliberately stopped. The sweeps are infinite loops (sleep + continueAsNew),
// so the only closed states they reach are explicit stops or a crash:
//
//   - TERMINATED / CANCELLED → leave it. Once terminated, stay Terminated:
//     a worker reboot must NOT silently restart it (this is the whole point —
//     "once it's terminated it should be Terminated properly").
//   - RUNNING / CONTINUED_AS_NEW / PAUSED → already alive, no-op.
//   - not found → start fresh (idempotent workflow id).
//   - anything else (COMPLETED / FAILED / TIMED_OUT) → an infinite sweep can
//     only land here via a crash; restart to restore delivery.
async function ensureSweep(
  client: Client,
  workflowType: string,
  workflowId: string,
  args: unknown[],
): Promise<void> {
  const handle = client.workflow.getHandle(workflowId);
  let status: string;
  try {
    const desc = await handle.describe();
    status = desc.status.name;
  } catch (err) {
    if (err instanceof WorkflowNotFoundError) {
      await client.workflow.start(workflowType, {
        taskQueue: TASK_QUEUE,
        workflowId,
        args,
      });
      console.log(`[temporal] ${workflowId} started`);
      return;
    }
    throw err;
  }

  if (status === "TERMINATED" || status === "CANCELLED") {
    console.log(
      `[temporal] ${workflowId} is ${status} — leaving it stopped (explicit stop respected)`,
    );
    return;
  }
  if (status === "RUNNING" || status === "CONTINUED_AS_NEW" || status === "PAUSED") {
    console.log(`[temporal] ${workflowId} already running (${status})`);
    return;
  }
  await client.workflow.start(workflowType, {
    taskQueue: TASK_QUEUE,
    workflowId,
    args,
  });
  console.log(`[temporal] ${workflowId} restarted (was ${status})`);
}

async function main(): Promise<void> {
  const connection = await NativeConnection.connect({ address: ADDRESS });

  const worker = await Worker.create({
    connection,
    namespace: NAMESPACE,
    taskQueue: TASK_QUEUE,
    workflowsPath: require.resolve("./workflows"),
    activities,
  });

  const client = new Client({ connection, namespace: NAMESPACE });

  // Sweep once (idempotent workflow id — a restarted worker resumes the
  // existing workflow instead of duplicating it, but respects a terminated one).
  await ensureSweep(client, "deliverySweep", "delivery-sweep", [100]);

  // Digest loop: every DIGEST_INTERVAL_SECONDS, batch unanswered notifications
  // (older than DIGEST_WINDOW) per user and mail them through Stalwart.
  const digestInterval = Number(process.env.DIGEST_INTERVAL_SECONDS ?? 3600);
  const digestWindow = process.env.DIGEST_WINDOW ?? "1 hour";
  await ensureSweep(client, "digestSweep", "digest-sweep", [digestWindow, digestInterval]);

  // Tier-2 lane: materialise contribution.* events into ledger entries. Runs alongside the
  // delivery sweep over the SAME outbox, partitioned by event type (coop_sweep_undelivered
  // excludes contribution.*), so the two consumers never race for a row.
  await ensureSweep(client, "tier2Sweep", "tier2-sweep", [100]);

  // Postiz sync: project opted-in groups into Postiz orgs + membership.
  await ensureSweep(client, "postizSyncSweep", "postiz-sync-sweep", [30]);

  await worker.run();
}

main().catch((err) => {
  console.error("[temporal] worker failed:", err);
  process.exit(1);
});
