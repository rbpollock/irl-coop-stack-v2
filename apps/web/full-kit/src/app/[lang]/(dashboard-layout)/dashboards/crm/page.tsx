import type { Metadata } from "next"

import { ActiveProjects } from "./_components/active-projects"
import { ActivityTimeline } from "./_components/activity-timeline"
import { CustomerSatisfaction } from "./_components/customer-satisfaction"
import { LeadSources } from "./_components/lead-sources"
import { Overview } from "./_components/overview"
import { RevenueTrend } from "./_components/revenue-trend"
import { SalesByCountry } from "./_components/sales-by-country"
import { SalesTrend } from "./_components/sales-trend"
import { TopSalesRepresentatives } from "./_components/top-sales-representatives"

// Define metadata for the page
// More info: https://nextjs.org/docs/app/building-your-application/optimizing/metadata
export const metadata: Metadata = {
  title: "CRM",
}

export default function CRMPage() {
  return (
    <section className="container grid gap-4 p-4 md:grid-cols-2">
      <Overview />
      <div className="col-span-full grid gap-4 md:grid-cols-4">
        <SalesTrend />
        <div className="grid gap-4 sm:grid-cols-2 md:grid-cols-1">
          <RevenueTrend />
          <LeadSources />
        </div>
      </div>
      <ActiveProjects />
      <ActivityTimeline />
      <SalesByCountry />
      <TopSalesRepresentatives />
      <CustomerSatisfaction />
    </section>
  )
}
