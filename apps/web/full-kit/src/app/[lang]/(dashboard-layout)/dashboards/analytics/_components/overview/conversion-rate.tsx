import type { OverviewType } from "../../types"

import {
  DashboardCardActionsDropdown,
  DashboardOverviewCardV3,
} from "@/components/dashboards/dashboard-card"
import { ConversionRateChart } from "./conversion-rate-chart"

export function ConversionRate({
  data,
}: {
  data: OverviewType["conversionRate"]
}) {
  return (
    <DashboardOverviewCardV3
      data={{
        value: data.averageValue,
        percentageChange: data.percentageChange,
      }}
      title="Conversion Rate"
      action={<DashboardCardActionsDropdown />}
      chart={<ConversionRateChart data={data.perMonth} />}
      formatStyle="percent"
    />
  )
}
