import type { Metadata } from "next"

import { NewVsReturningVisitors } from "../../../dashboards/analytics/_components/new-vs-returning-visitors"
import { Overview as OverviewV3 } from "../../../dashboards/analytics/_components/overview"
import { LeadSources } from "../../../dashboards/crm/_components/lead-sources"
import { Overview } from "../../../dashboards/crm/_components/overview"
import { RevenueTrend } from "../../../dashboards/crm/_components/revenue-trend"
import { CustomerInsights } from "../../../dashboards/ecommerce/_components/customer-insights"
import { GenderDistribution } from "../../../dashboards/ecommerce/_components/gender-distribution"
import { Overview as OverviewV2 } from "../../../dashboards/ecommerce/_components/overview"

// Define metadata for the page
// More info: https://nextjs.org/docs/app/building-your-application/optimizing/metadata
export const metadata: Metadata = {
  title: "Statistics Cards",
}

export default function StatisticsCardsPage() {
  return (
    <section className="container grid gap-4 p-4 md:grid-cols-2">
      <Overview />
      <OverviewV2 />
      <OverviewV3 />
      <div className="col-span-full grid gap-4 md:grid-cols-4">
        <RevenueTrend />
        <LeadSources />
        <GenderDistribution />
        <NewVsReturningVisitors />
      </div>
      <CustomerInsights />
    </section>
  )
}
