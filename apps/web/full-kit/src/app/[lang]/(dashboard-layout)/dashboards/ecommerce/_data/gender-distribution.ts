import type { GenderDistributionType } from "../../analytics/types"

export const genderDistributionData: GenderDistributionType[] = [
  {
    name: "Male",
    value: 12500,
    percentage: 0.5363,
    fill: "hsl(var(--chart-1))",
    x: 1.75,
    y: 3,
  },
  {
    name: "Female",
    value: 10000,
    percentage: 0.4293,
    fill: "hsl(var(--chart-2))",
    x: 2.75,
    y: 2,
  },
  {
    name: "Other",
    value: 800,
    percentage: 0.0343,
    fill: "hsl(var(--chart-3))",
    x: 3.75,
    y: 3.5,
  },
]
