import { salesRepresentativeData } from "../_data/top-sales-representatives"

import {
  DashboardCard,
  DashboardCardActionsDropdown,
} from "@/components/dashboards/dashboard-card"
import { TopSalesRepresentativesList } from "./top-sales-representatives-list"

export function TopSalesRepresentatives() {
  return (
    <DashboardCard
      title="Top Sales Representatives"
      period={salesRepresentativeData.period}
      action={<DashboardCardActionsDropdown />}
    >
      <TopSalesRepresentativesList
        data={salesRepresentativeData.representatives}
      />
    </DashboardCard>
  )
}
