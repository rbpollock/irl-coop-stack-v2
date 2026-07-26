import { BadgePercent, HandCoins, Users } from "lucide-react"

import { overviewData } from "../_data/overview"

import {
  DashboardCardActionsDropdown,
  DashboardOverviewCard,
} from "@/components/dashboards/dashboard-card"

export function Overview() {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 md:col-span-2 md:grid-cols-4">
      <DashboardOverviewCard
        data={overviewData.totalSales}
        title="Total Sales"
        period={overviewData.totalSales.period}
        action={<DashboardCardActionsDropdown />}
        icon={BadgePercent}
        formatStyle="currency"
      />
      <DashboardOverviewCard
        data={overviewData.totalProfit}
        title="Total Profit"
        period={overviewData.totalProfit.period}
        action={<DashboardCardActionsDropdown />}
        icon={HandCoins}
        formatStyle="currency"
      />
      <DashboardOverviewCard
        data={overviewData.revenueGrowth}
        title="Revenue Growth"
        period={overviewData.revenueGrowth.period}
        action={<DashboardCardActionsDropdown />}
        icon={HandCoins}
        formatStyle="currency"
      />
      <DashboardOverviewCard
        data={overviewData.newCustomers}
        title="New Customers"
        period={overviewData.newCustomers.period}
        action={<DashboardCardActionsDropdown />}
        icon={Users}
      />
    </div>
  )
}
