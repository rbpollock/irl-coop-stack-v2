import { revenueBySourceData } from "../_data/revenue-by-source"

import {
  DashboardCard,
  DashboardCardActionsDropdown,
} from "@/components/dashboards/dashboard-card"
import { RevenueBySourceChart } from "./revenue-by-source-chart"
import { RevenueBySourceList } from "./revenue-by-source-list"
import { RevenueBySourceSummary } from "./revenue-by-source-summary"

export function RevenueBySource() {
  return (
    <DashboardCard
      title="Revenue by Source"
      period={revenueBySourceData.period}
      action={<DashboardCardActionsDropdown />}
      size="sm"
      contentClassName="gap-y-3"
    >
      <RevenueBySourceSummary data={revenueBySourceData.summary} />
      <RevenueBySourceChart data={revenueBySourceData.sources} />
      <RevenueBySourceList data={revenueBySourceData.sources} />
    </DashboardCard>
  )
}
