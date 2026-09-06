import type { Metadata } from "next"

import NeedsOffersMockup from "@/components/dashboards/needs-offers-mockup"

// Mockup only — the needs/offers board, trade-chain view, and expediting detail.
// No backend wiring yet; see docs/design/needs-offers-matching.md for the spec.
export const metadata: Metadata = {
  title: "Needs & Offers",
}

export default function NeedsOffersPage() {
  return (
    <section className="container grid gap-4 p-4">
      <NeedsOffersMockup />
    </section>
  )
}
