import type { Metadata } from "next"

import { ConversionFunnel } from "../../../dashboards/analytics/_components/conversion-funnel"
import { PerformanceOverTime } from "../../../dashboards/analytics/_components/performance-over-time"
import { TrafficSources } from "../../../dashboards/analytics/_components/traffic-sources"
import { SalesByCountry } from "../../../dashboards/crm/_components/sales-by-country"
import { SalesTrend } from "../../../dashboards/crm/_components/sales-trend"
import { ChurnRate } from "../../../dashboards/ecommerce/_components/churn-rate"
import { RevenueBySource } from "../../../dashboards/ecommerce/_components/revenue-by-source"
import { SalesTrend as SalesTrendV2 } from "../../../dashboards/ecommerce/_components/sales-trend"

// Define metadata for the page
// More info: https://nextjs.org/docs/app/building-your-application/optimizing/metadata
export const metadata: Metadata = {
  title: "Analytics Cards",
}

export default function AnalyticsCardsPage() {
  return (
    <section className="container grid gap-4 p-4 md:grid-cols-2">
      <div className="col-span-full">
        <SalesTrend />
      </div>
      <TrafficSources />
      <SalesTrendV2 />
      <PerformanceOverTime />
      <SalesByCountry />
      <ChurnRate />
      <RevenueBySource />
      <ConversionFunnel />
    </section>
  )
}
