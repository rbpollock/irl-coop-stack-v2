import { Client, WorkflowNotFoundError } from "@temporalio/client";

async function main() {
  const client = new Client({
    namespace: process.env.TEMPORAL_NAMESPACE ?? "coop",
  });
  for (const id of ["delivery-sweep", "digest-sweep"]) {
    try {
      const desc = await client.workflow.getHandle(id).describe();
      console.log(`${id}: status=${desc.status.name} runId=${desc.runId}`);
    } catch (err) {
      if (err instanceof WorkflowNotFoundError) {
        console.log(`${id}: NOT FOUND (would start fresh)`);
      } else {
        console.log(`${id}: ERROR ${(err as Error).name}: ${(err as Error).message}`);
      }
    }
  }
}

main().catch((e) => {
  console.error("FAILED:", (e as Error).message);
  process.exit(1);
});
