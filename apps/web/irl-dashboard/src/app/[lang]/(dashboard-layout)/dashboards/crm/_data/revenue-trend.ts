import type { RevenueTrendType } from "../types"

export const revenueTrendData: RevenueTrendType = {
  period: "2024",
  summary: {
    totalRevenue: 80000,
    totalPercentageChange: 0.25,
  },
  revenueTrends: [
    { month: "January", revenue: 5000 },
    { month: "February", revenue: 5500 },
    { month: "March", revenue: 5000 },
    { month: "April", revenue: 6000 },
    { month: "May", revenue: 6500 },
    { month: "June", revenue: 7000 },
    { month: "July", revenue: 7250 },
    { month: "August", revenue: 7250 },
    { month: "September", revenue: 6500 },
    { month: "October", revenue: 6000 },
    { month: "November", revenue: 7000 },
    { month: "December", revenue: 8000 },
  ],
}
