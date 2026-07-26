import type { DynamicIconNameType } from "@/types"

export interface MetricType {
  period: string
  value: number
  percentageChange: number
}

export interface OverviewType {
  totalSales: MetricType
  totalProfit: MetricType
  revenueGrowth: MetricType
  newCustomers: MetricType
}

export interface SalesTrendType {
  period: string
  summary: {
    totalLead: number
    totalProposal: number
    totalNegotiation: number
    totalClosed: number
  }
  monthly: Array<{
    month: string
    lead: number
    proposal: number
    negotiation: number
    closed: number
  }>
}

export interface SalesRepresentativeType {
  period: string
  representatives: Array<{
    name: string
    avatar: string
    email: string
    sales: number
  }>
}

export interface LeadSourceType {
  period: string
  summary: {
    totalLeads: number
  }
  leads: {
    socialMedia: number
    emailCampaigns: number
    referrals: number
    website: number
    other: number
  }
}

export interface CustomerSatisfactionType {
  period: string
  summary: {
    name: string
    value: number
  }
  feedbacks: Array<{
    name: string
    email: string
    avatar: string
    rating: number
    feedbackMessage: string
    createdAt: Date
  }>
}

export interface ActiveProjectType {
  name: string
  progress: number
  startDate: Date
  dueDate: Date
  status: "On Track" | "At Risk" | "On Hold"
}

export interface SalesByCountryType {
  period: string
  countries: Array<{
    countryName: string
    countryCode: string
    sales: number
  }>
}

export interface RevenueTrendType {
  period: string
  summary: {
    totalRevenue: number
    totalPercentageChange: number
  }
  revenueTrends: Array<{ month: string; revenue: number }>
}

export type ActivityType =
  | "email"
  | "supportTicket"
  | "dealUpdate"
  | "call"
  | "meeting"
  | "note"

export interface AssignedMemberType {
  name: string
  avatar: string
  href: string
}

export interface ActivityTimelineType {
  period: string
  activities: Array<{
    type: ActivityType
    iconName: DynamicIconNameType
    fill: string
    title: string
    description: string
    status?: string
    date: string
    assignedMembers: AssignedMemberType[]
  }>
}
