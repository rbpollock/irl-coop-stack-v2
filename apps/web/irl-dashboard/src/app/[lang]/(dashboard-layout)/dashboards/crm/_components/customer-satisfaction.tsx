import { customerSatisfactionData } from "../_data/customer-satisfaction"

import {
  DashboardCard,
  DashboardCardActionsDropdown,
} from "@/components/dashboards/dashboard-card"
import { CustomerSatisfactionCarousel } from "./customer-satisfaction-carousel"
import { CustomerSatisfactionChart } from "./customer-satisfaction-chart"

export function CustomerSatisfaction() {
  return (
    <DashboardCard
      title="Customer Satisfaction"
      period={customerSatisfactionData.period}
      action={<DashboardCardActionsDropdown />}
      className="col-span-full"
      contentClassName="h-auto items-center gap-6 md:h-64 md:flex-row"
    >
      <CustomerSatisfactionChart data={customerSatisfactionData.summary} />
      <CustomerSatisfactionCarousel data={customerSatisfactionData.feedbacks} />
    </DashboardCard>
  )
}
