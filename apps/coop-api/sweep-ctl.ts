// Operator control for the self-scheduling coop sweeps (mirrors worker.ts).
//   npx ts-node sweep-ctl.ts status [workflowId]
//   npx ts-node sweep-ctl.ts terminate <workflowId>
// A TERMINATED sweep stays terminated across worker reboots (see ensureSweep).
import { NativeConnection } from "@temporalio/worker";
import { Client } from "@temporalio/client";

const ADDRESS = process.env.TEMPORAL_ADDRESS ?? "localhost:7233";
const NS = process.env.TEMPORAL_NAMESPACE ?? "coop";
const action = process.argv[2] ?? "status";
const target = process.argv[3] ?? "digest-sweep";

async function main() {
  const connection = await NativeConnection.connect({ address: ADDRESS });
  const client = new Client({ connection, namespace: NS });
  const h = client.workflow.getHandle(target);
  try {
    const d = await h.describe();
    console.log(`${target}: ${d.status.name} runId=${d.runId} start=${d.startTime?.toISOString()}`);
    if (action === "terminate") {
      await h.terminate("operator stop: SMTP 587 blocked from host, stopping retry storm");
      console.log(`${target}: TERMINATED`);
    }
  } catch (e) {
    console.log(`${target}: ${(e as Error).name}: ${(e as Error).message}`);
  } finally {
    await connection.close();
  }
}
main().catch((e) => {
  console.error("FAILED:", (e as Error).message);
  process.exit(1);
});