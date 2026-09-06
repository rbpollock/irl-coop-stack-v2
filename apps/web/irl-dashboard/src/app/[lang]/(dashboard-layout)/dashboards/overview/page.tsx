import type { Metadata } from "next"

import { PhoneHome } from "@/components/dashboards/phone-home"

export const metadata: Metadata = {
  title: "IRL Co-op Dashboard",
}

// The coop's home screen: the phone/tablet home — widget cards (attention,
// situation, commons) above a grid of app icons.
export default function IRLCoopDashboardPage() {
  return (
    <section className="container space-y-6 p-4">
      <PhoneHome />
    </section>
  )
}
