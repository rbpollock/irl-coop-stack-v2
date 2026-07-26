import type { Metadata } from "next"

import { ConversionFunnel } from "./_components/conversion-funnel"
import { EngagementByDevice } from "./_components/engagement-by-device"
import { NewVsReturningVisitors } from "./_components/new-vs-returning-visitors"
import { Overview } from "./_components/overview"
import { PerformanceOverTime } from "./_components/performance-over-time"
import { TrafficSources } from "./_components/traffic-sources"
import { VisitorsByCountry } from "./_components/visitors-by-country"

// Define metadata for the page
// More info: https://nextjs.org/docs/app/building-your-application/optimizing/metadata
export const metadata: Metadata = {
  title: "Analytics",
}

export default function AnalyticsPage() {
  return (
    <section className="container grid gap-4 p-4 md:grid-cols-2">
      <Overview />
      <TrafficSources />
      <div className="space-y-4">
        <ConversionFunnel />
        <NewVsReturningVisitors />
      </div>
      <PerformanceOverTime />
      <VisitorsByCountry />
      <EngagementByDevice />
    </section>
  )
}
