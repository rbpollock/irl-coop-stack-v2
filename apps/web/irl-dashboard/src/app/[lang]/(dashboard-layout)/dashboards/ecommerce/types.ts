export interface MetricType {
  value: number
  percentageChange: number
  period: string
}

export interface OverviewType {
  totalSales: MetricType
  revenueSummary: MetricType
  numberOfOrders: MetricType
  averageOrderValue: MetricType
}

export interface SalesTrendType {
  period: string
  summary: {
    lowestSales: { date: number; sales: number }
    highestSales: { date: number; sales: number }
    avgSales: number
    totalSales: number
  }
  salesTrends: Array<{ date: number; sales: number }>
}

export interface TopProductType {
  period: string
  products: Array<{
    name: string
    sales: {
      value: number
      percentageChange: number
    }
    revenue: {
      value: number
      percentageChange: number
    }
    order: number
    image: string
    sku: string
  }>
}

export interface CustomerInsightsType {
  period: string
  totalCustomers: number
  newCustomers: number
  returningCustomers: number
  vipCustomers: number
}

export interface InvoiceType {
  invoiceId: string
  customerName: string
  orderDate: string
  dueDate: string
  totalAmount: number
  deliveryStatus:
    | "Delivered"
    | "Shipped"
    | "In Transit"
    | "Processing"
    | "Pending"
}

export interface RevenueBySourceType {
  period: string
  summary: {
    totalRevenue: number
    percentageChange: number
  }
  sources: Array<{
    name: string
    value: number
    percentage: number
    fill: string
  }>
}

export interface ChurnRateType {
  period: string
  summary: {
    totalCustomers: number
    totalLostCustomers: number
    averageChurnRate: number
  }
  months: Array<{
    month: string
    totalCustomers: number
    lostCustomers: number
    churnRate: number
  }>
}
