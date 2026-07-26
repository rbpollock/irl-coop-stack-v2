import { salesTrendData } from "../_data/sales-trend"

import {
  DashboardCard,
  DashboardCardActionsDropdown,
} from "@/components/dashboards/dashboard-card"
import { SalesTrendChart } from "./sales-trend-chart"
import { SalesTrendSummary } from "./sales-trend-summary"

export function SalesTrend() {
  return (
    <DashboardCard
      title="Sales Trend"
      period={salesTrendData.period}
      action={<DashboardCardActionsDropdown />}
      size="lg"
    >
      <SalesTrendSummary data={salesTrendData.summary} />
      <SalesTrendChart data={salesTrendData.salesTrends} />
    </DashboardCard>
  )
}
