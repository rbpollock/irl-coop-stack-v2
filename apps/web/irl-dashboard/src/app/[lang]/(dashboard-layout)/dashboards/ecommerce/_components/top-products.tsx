import { topProductsData } from "../_data/top-products"

import {
  DashboardCard,
  DashboardCardActionsDropdown,
} from "@/components/dashboards/dashboard-card"
import { TopProductsList } from "./top-products-list"

export function TopProducts() {
  return (
    <DashboardCard
      title="Top Products"
      period={topProductsData.period}
      action={<DashboardCardActionsDropdown />}
      size="lg"
    >
      <TopProductsList data={topProductsData.products} />
    </DashboardCard>
  )
}
