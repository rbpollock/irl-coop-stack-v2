import type { Metadata } from "next"

import { ChurnRate } from "./_components/churn-rate"
import { CustomerInsights } from "./_components/customer-insights"
import { GenderDistribution } from "./_components/gender-distribution"
import { Invoices } from "./_components/invoices"
import { Overview } from "./_components/overview"
import { RevenueBySource } from "./_components/revenue-by-source"
import { SalesTrend } from "./_components/sales-trend"
import { TopProducts } from "./_components/top-products"

// Define metadata for the page
// More info: https://nextjs.org/docs/app/building-your-application/optimizing/metadata
export const metadata: Metadata = {
  title: "Ecommerce",
}

export default function EcommercePage() {
  return (
    <section className="container grid gap-4 p-4 md:grid-cols-2">
      <Overview />
      <ChurnRate />
      <RevenueBySource />
      <div className="col-span-full grid gap-4 md:grid-cols-4">
        <CustomerInsights />
        <GenderDistribution />
      </div>
      <SalesTrend />
      <TopProducts />
      <Invoices />
    </section>
  )
}
