import type { RevenueBySourceType } from "../types"

import { formatCurrency } from "@/lib/utils"

import { PercentageChangeBadge } from "@/components/dashboards/percentage-change-badge"

export function RevenueBySourceSummary({
  data,
}: {
  data: RevenueBySourceType["summary"]
}) {
  return (
    <div className="flex items-end gap-x-1">
      <p className="text-2xl font-semibold">
        {formatCurrency(data.totalRevenue)}
      </p>
      <PercentageChangeBadge
        value={data.percentageChange}
        variant="ghost"
        className="p-0"
      />
    </div>
  )
}
