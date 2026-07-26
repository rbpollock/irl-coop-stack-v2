import type { CurrentPlanType } from "../types"

export const currentPlanData: CurrentPlanType = {
  plan: {
    name: "Business Pro",
    price: "$49/month",
    description: "Ideal for growing teams and businesses",
  },
  stats: {
    activeProjects: {
      value: 15,
      max: 20,
      progress: 75,
    },
    teamMembers: {
      value: 18,
      max: 25,
      progress: 72,
    },
    storageUsed: {
      value: 4500000000,
      max: 10000000000,
      progress: 45,
    },
  },
  activityThisMonth: [
    {
      iconName: "Briefcase",
      count: 32,
      label: "New Projects",
    },
    {
      iconName: "Users",
      count: 128,
      label: "New Clients",
    },
    {
      iconName: "FileText",
      count: 287,
      label: "Documents Created",
    },
    {
      iconName: "ChartNoAxesColumn",
      count: 14,
      label: "Reports Generated",
    },
  ],
  billingInfo: {
    nextBillingDate: new Date(new Date().setDate(new Date().getDate() + 2)), // 2 days from the current date
    amountDue: 49,
  },
}
