import { trafficSourcesData } from "../_data/traffic-sources"

import {
  DashboardCard,
  DashboardCardActionsDropdown,
} from "@/components/dashboards/dashboard-card"
import { TrafficSourcesChart } from "./traffic-sources-chart"
import { TrafficSourcesTable } from "./traffic-sources-table"

export function TrafficSources() {
  return (
    <DashboardCard
      title="Traffic Sources"
      period={trafficSourcesData.period}
      action={<DashboardCardActionsDropdown />}
      size="lg"
    >
      <TrafficSourcesChart data={trafficSourcesData.sources} />
      <TrafficSourcesTable data={trafficSourcesData.sources} />
    </DashboardCard>
  )
}
