import { salesByCountryData } from "../_data/sales-by-country"

import {
  DashboardCard,
  DashboardCardActionsDropdown,
} from "@/components/dashboards/dashboard-card"
import { SalesByCountryChart } from "./sales-by-country-chart"

export function SalesByCountry() {
  return (
    <DashboardCard
      title="Sales by Country"
      period={salesByCountryData.period}
      action={<DashboardCardActionsDropdown />}
    >
      <SalesByCountryChart data={salesByCountryData.countries} />
    </DashboardCard>
  )
}
