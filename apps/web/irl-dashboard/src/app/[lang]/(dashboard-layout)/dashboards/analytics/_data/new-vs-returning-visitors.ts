import type { NewVsReturningVisitorsType } from "../types"

export const newVsReturningVisitors: NewVsReturningVisitorsType = {
  visitors: {
    new: {
      value: 7234,
      percentageChange: 0.65,
      fill: "hsl(var(--chart-1))",
    },
    returning: {
      value: 4128,
      percentageChange: 0.35,
      fill: "hsl(var(--chart-2))",
    },
  },
}
