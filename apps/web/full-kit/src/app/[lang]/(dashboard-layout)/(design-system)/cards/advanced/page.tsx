import type { Metadata } from "next"

import { EngagementByDevice } from "../../../dashboards/analytics/_components/engagement-by-device"
import { VisitorsByCountry } from "../../../dashboards/analytics/_components/visitors-by-country"
import { ActiveProjects } from "../../../dashboards/crm/_components/active-projects"
import { ActivityTimeline } from "../../../dashboards/crm/_components/activity-timeline"
import { CustomerSatisfaction } from "../../../dashboards/crm/_components/customer-satisfaction"
import { TopSalesRepresentatives } from "../../../dashboards/crm/_components/top-sales-representatives"
import { Invoices } from "../../../dashboards/ecommerce/_components/invoices"
import { TopProducts } from "../../../dashboards/ecommerce/_components/top-products"

// Define metadata for the page
// More info: https://nextjs.org/docs/app/building-your-application/optimizing/metadata
export const metadata: Metadata = {
  title: "Advanced Cards",
}

export default function AdvancedCardsPage() {
  return (
    <section className="container grid gap-4 p-4 md:grid-cols-2">
      <ActiveProjects />
      <ActivityTimeline />
      <VisitorsByCountry />
      <TopSalesRepresentatives />
      <TopProducts />
      <EngagementByDevice />
      <CustomerSatisfaction />
      <Invoices />
    </section>
  )
}
