import type { Metadata } from "next"

import StackHealth from "@/components/dashboards/stack-health"

// Shard Nodes — the network's health at a glance. This is where the
// declared-vs-running stack reconciler lives (GET /api/v1/stack/status):
// the tree in infra/instances/dev/ is the declared state, docker is the
// running state, the difference is drift.
export const metadata: Metadata = {
  title: "Shard Nodes",
}

export default function ShardNodesPage() {
  return (
    <section className="container grid gap-4 p-4">
      <StackHealth />
    </section>
  )
}
