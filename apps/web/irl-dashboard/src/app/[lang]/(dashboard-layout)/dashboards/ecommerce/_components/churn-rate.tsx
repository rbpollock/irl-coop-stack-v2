import { churnRateData } from "../_data/churn-rate"

import {
  DashboardCard,
  DashboardCardActionsDropdown,
} from "@/components/dashboards/dashboard-card"
import { ChurnRateChart } from "./churn-rate-chart"
import { ChurnRateSummary } from "./churn-rate-summary"

export function ChurnRate() {
  return (
    <DashboardCard
      title="Churn Rate"
      period={churnRateData.period}
      action={<DashboardCardActionsDropdown />}
      size="sm"
    >
      <ChurnRateSummary data={churnRateData.summary} />
      <ChurnRateChart data={churnRateData.months} />
    </DashboardCard>
  )
}
