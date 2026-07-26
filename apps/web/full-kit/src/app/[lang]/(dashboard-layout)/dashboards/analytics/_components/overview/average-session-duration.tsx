import type { OverviewType } from "../../types"

import {
  DashboardCardActionsDropdown,
  DashboardOverviewCardV3,
} from "@/components/dashboards/dashboard-card"
import { AverageSessionDurationChart } from "./average-session-duration-chart"

export function AverageSessionDuration({
  data,
}: {
  data: OverviewType["averageSessionDuration"]
}) {
  return (
    <DashboardOverviewCardV3
      data={{
        value: data.averageValue,
        percentageChange: data.percentageChange,
      }}
      title="Avg. Session Duration"
      action={<DashboardCardActionsDropdown />}
      chart={<AverageSessionDurationChart data={data.perMonth} />}
      formatStyle="duration"
    />
  )
}
