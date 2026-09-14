import type { Metadata } from "next"

import DuesPanel from "@/components/dashboards/dues-panel"

// Dues — a projection over Tier-1/Tier-2/authority records, not a stored flag.
// See docs/design/tier2-entry-model.md §5.1 (what dues is), §5.3 (why the policy is a
// table rather than a rules engine) and §5.4 (what this does not do yet).
export const metadata: Metadata = {
  title: "Dues",
}

export default function DuesPage() {
  return (
    <section className="container grid gap-4 p-4">
      <DuesPanel />
    </section>
  )
}
