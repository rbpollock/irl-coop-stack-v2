import type { OverviewType } from "../../types"

import {
  DashboardCardActionsDropdown,
  DashboardOverviewCardV3,
} from "@/components/dashboards/dashboard-card"
import { BounceRateChart } from "./bounce-rate-chart"

export function BounceRate({ data }: { data: OverviewType["bounceRate"] }) {
  return (
    <DashboardOverviewCardV3
      data={{
        value: data.averageValue,
        percentageChange: data.percentageChange,
      }}
      title="Bounce Rate"
      action={<DashboardCardActionsDropdown />}
      chart={<BounceRateChart data={data.perMonth} />}
      formatStyle="percent"
    />
  )
}
