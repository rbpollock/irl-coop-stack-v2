import type { ChurnRateType } from "../types"

import { formatPercent } from "@/lib/utils"

export function ChurnRateSummary({ data }: { data: ChurnRateType["summary"] }) {
  return (
    <div className="grid grid-cols-3 justify-items-center gap-3">
      <div>
        <p className="text-2xl font-semibold">
          {data.totalCustomers.toLocaleString()}
        </p>
        <h3 className="inline-flex items-baseline gap-x-1 text-sm text-muted-foreground">
          <div className="h-2.5 w-2.5 bg-chart-2 rounded-sm" />
          <span>Total Customers</span>
        </h3>
      </div>
      <div>
        <p className="text-2xl font-semibold">
          {data.totalLostCustomers.toLocaleString()}
        </p>
        <h3 className="inline-flex items-baseline gap-x-1 text-sm text-muted-foreground">
          <div className="h-2.5 w-2.5 bg-chart-1 rounded-sm" />
          <span>Total Lost Customers</span>
        </h3>
      </div>
      <div>
        <p className="text-2xl font-semibold">
          {formatPercent(data.averageChurnRate)}
        </p>
        <h3 className="inline-flex items-baseline gap-x-1 text-sm text-muted-foreground">
          <div className="h-2.5 w-2.5 bg-white border border-border rounded-sm" />
          <span>Average Churn Rate</span>
        </h3>
      </div>
    </div>
  )
}
