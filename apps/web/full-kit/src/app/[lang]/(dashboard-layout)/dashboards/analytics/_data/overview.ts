import type { OverviewType } from "../types"

export const overviewData: OverviewType = {
  uniqueVisitors: {
    averageValue: 15091.67,
    percentageChange: 0.07,
    perMonth: [
      { month: "January", value: 12000 },
      { month: "February", value: 16000 },
      { month: "March", value: 15050 },
      { month: "April", value: 14000 },
      { month: "May", value: 17500 },
      { month: "June", value: 16000 },
    ],
  },
  averageSessionDuration: {
    averageValue: 73333.33,
    percentageChange: -0.04,
    perMonth: [
      { month: "January", value: 110000, fill: "hsl(var(--chart-1))" },
      { month: "February", value: -90000, fill: "hsl(var(--chart-2))" },
      { month: "March", value: 220000, fill: "hsl(var(--chart-1))" },
      { month: "April", value: -130000, fill: "hsl(var(--chart-2))" },
      { month: "May", value: 135000, fill: "hsl(var(--chart-1))" },
      { month: "June", value: 195000, fill: "hsl(var(--chart-1))" },
    ],
  },
  bounceRate: {
    averageValue: 0.5933,
    percentageChange: 0.05,
    perMonth: [
      { month: "January", value: 0.12 },
      { month: "February", value: 0.55 },
      { month: "March", value: 0.68 },
      { month: "April", value: 0.48 },
      { month: "May", value: 0.7 },
      { month: "June", value: 0.53 },
    ],
  },
  conversionRate: {
    averageValue: 0.5631,
    percentageChange: 0.038,
    perMonth: [
      { month: "January", value: 0.4 },
      { month: "February", value: 0.48 },
      { month: "March", value: 0.43 },
      { month: "April", value: 0.6 },
      { month: "May", value: 0.52 },
      { month: "June", value: 0.75 },
    ],
  },
}
