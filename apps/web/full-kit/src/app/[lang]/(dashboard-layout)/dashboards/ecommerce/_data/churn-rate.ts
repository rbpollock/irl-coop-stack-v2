import type { ChurnRateType } from "../types"

export const churnRateData: ChurnRateType = {
  period: "Current year",
  summary: {
    totalCustomers: 9400,
    totalLostCustomers: 7300,
    averageChurnRate: 0.0815,
  },
  months: [
    {
      month: "January",
      totalCustomers: 5000,
      lostCustomers: 400,
      churnRate: 0.08,
    },
    {
      month: "February",
      totalCustomers: 5400,
      lostCustomers: 350,
      churnRate: 0.0648,
    },
    {
      month: "March",
      totalCustomers: 5800,
      lostCustomers: 500,
      churnRate: 0.0862,
    },
    {
      month: "April",
      totalCustomers: 6200,
      lostCustomers: 450,
      churnRate: 0.0726,
    },
    {
      month: "May",
      totalCustomers: 6600,
      lostCustomers: 600,
      churnRate: 0.0909,
    },
    {
      month: "June",
      totalCustomers: 7000,
      lostCustomers: 550,
      churnRate: 0.0786,
    },
    {
      month: "July",
      totalCustomers: 7400,
      lostCustomers: 700,
      churnRate: 0.0946,
    },
    {
      month: "August",
      totalCustomers: 7800,
      lostCustomers: 650,
      churnRate: 0.0833,
    },
    {
      month: "September",
      totalCustomers: 8200,
      lostCustomers: 800,
      churnRate: 0.0976,
    },
    {
      month: "October",
      totalCustomers: 8600,
      lostCustomers: 750,
      churnRate: 0.0872,
    },
    {
      month: "November",
      totalCustomers: 9000,
      lostCustomers: 900,
      churnRate: 0.1,
    },
    {
      month: "December",
      totalCustomers: 9400,
      lostCustomers: 600,
      churnRate: 0.0638,
    },
  ],
}
