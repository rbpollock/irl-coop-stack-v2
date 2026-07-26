import type { SalesTrendType } from "../types"

export const salesTrendData: SalesTrendType = {
  period: "Last week",
  summary: {
    lowestSales: { date: 1694025600000, sales: 85000 },
    highestSales: { date: 1693939200000, sales: 162000 },
    avgSales: 120500,
    totalSales: 3615000,
  },
  salesTrends: [
    { date: 1693593600000, sales: 102000 },
    { date: 1693680000000, sales: 158000 },
    { date: 1693766400000, sales: 128000 },
    { date: 1693852800000, sales: 92000 },
    { date: 1693939200000, sales: 162000 },
    { date: 1694025600000, sales: 85000 },
    { date: 1694112000000, sales: 116000 },
  ],
}
