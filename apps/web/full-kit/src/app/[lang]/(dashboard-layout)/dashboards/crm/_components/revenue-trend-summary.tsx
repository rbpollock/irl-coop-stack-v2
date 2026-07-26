"use client"

import type { RevenueTrendType } from "../types"

import { formatCurrency } from "@/lib/utils"

import { PercentageChangeBadge } from "@/components/dashboards/percentage-change-badge"

export function RevenueTrendSummary({
  data,
}: {
  data: RevenueTrendType["summary"]
}) {
  return (
    <div className="flex flex-col items-start bg-accent text-accent-foreground py-2 px-4 rounded-lg">
      <h3 className="text-sm text-muted-foreground">Total Revenue</h3>
      <div className="inline-flex flex-wrap items-baseline gap-x-1">
        <p className="text-2xl font-semibold">
          {formatCurrency(data.totalRevenue)}
        </p>
        <PercentageChangeBadge
          value={data.totalPercentageChange}
          variant="ghost"
          className="p-0"
        />
      </div>
    </div>
  )
}
