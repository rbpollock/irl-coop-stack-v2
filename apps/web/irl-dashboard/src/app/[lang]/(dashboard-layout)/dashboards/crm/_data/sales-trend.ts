import type { SalesTrendType } from "../types"

export const salesTrendData: SalesTrendType = {
  period: "Last year",
  summary: {
    totalLead: 2200,
    totalProposal: 1550,
    totalNegotiation: 900,
    totalClosed: 700,
  },
  monthly: [
    { month: "January", lead: 250, proposal: 200, negotiation: 80, closed: 50 },
    {
      month: "February",
      lead: 230,
      proposal: 190,
      negotiation: 70,
      closed: 55,
    },
    { month: "March", lead: 200, proposal: 180, negotiation: 75, closed: 60 },
    { month: "April", lead: 180, proposal: 160, negotiation: 85, closed: 65 },
    { month: "May", lead: 190, proposal: 140, negotiation: 90, closed: 50 },
    { month: "June", lead: 170, proposal: 130, negotiation: 95, closed: 45 },
    { month: "July", lead: 160, proposal: 120, negotiation: 100, closed: 70 },
    { month: "August", lead: 150, proposal: 130, negotiation: 110, closed: 80 },
    {
      month: "September",
      lead: 200,
      proposal: 150,
      negotiation: 120,
      closed: 90,
    },
    {
      month: "October",
      lead: 220,
      proposal: 170,
      negotiation: 100,
      closed: 85,
    },
    {
      month: "November",
      lead: 240,
      proposal: 190,
      negotiation: 70,
      closed: 70,
    },
    {
      month: "December",
      lead: 210,
      proposal: 220,
      negotiation: 100,
      closed: 80,
    },
  ],
}
