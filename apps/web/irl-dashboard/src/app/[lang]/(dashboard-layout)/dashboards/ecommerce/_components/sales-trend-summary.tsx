import type { SalesTrendType } from "../types"

import { formatCurrency, formatDateShort } from "@/lib/utils"

import { SalesTrendSummaryItem } from "./sales-trend-summary-item"

export function SalesTrendSummary({
  data,
}: {
  data: SalesTrendType["summary"]
}) {
  return (
    <ul className="flex flex-col justify-around gap-4 sm:flex-row">
      <div className="flex flex-wrap justify-around gap-4 md:flex-col">
        <SalesTrendSummaryItem
          title="Highest Sales"
          value={formatCurrency(data.highestSales.sales)}
          description={`on ${formatDateShort(data.highestSales.date)}`}
        />
        <SalesTrendSummaryItem
          title="Lowest Sales"
          value={formatCurrency(data.lowestSales.sales)}
          description={`on ${formatDateShort(data.lowestSales.date)}`}
        />
      </div>
      <div className="flex flex-wrap justify-around gap-4 md:flex-col">
        <SalesTrendSummaryItem
          title="Total Sales"
          value={formatCurrency(data.totalSales)}
          description="for the period"
        />
        <SalesTrendSummaryItem
          title="Avg. Sales"
          value={formatCurrency(data.avgSales)}
          description="per day"
        />
      </div>
    </ul>
  )
}
