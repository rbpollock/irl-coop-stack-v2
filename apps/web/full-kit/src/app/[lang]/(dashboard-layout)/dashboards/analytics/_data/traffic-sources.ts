import type { TrafficSourcesType } from "../types"

export const trafficSourcesData: TrafficSourcesType = {
  period: "Last month",
  sources: [
    {
      name: "Direct",
      visitors: 4000,
      fill: "hsl(var(--chart-1))",
      percentageChange: 0.3,
      icon: "MousePointer",
    },
    {
      name: "Referral",
      visitors: 2500,
      fill: "hsl(var(--chart-2))",
      percentageChange: 0.25,
      icon: "Link",
    },
    {
      name: "Social Media",
      visitors: 2000,
      fill: "hsl(var(--chart-3))",
      percentageChange: 0.2,
      icon: "Users",
    },
    {
      name: "Search Engine",
      visitors: 1000,
      fill: "hsl(var(--chart-4))",
      percentageChange: -0.1,
      icon: "Search",
    },
    {
      name: "Email",
      visitors: 500,
      fill: "hsl(var(--chart-5))",
      percentageChange: 0.05,
      icon: "Mail",
    },
  ],
}
