"use client"

import { Eye, RefreshCw } from "lucide-react"

import type { PerformanceOverTimeType } from "../types"

import { Badge } from "@/components/ui/badge"

export function PerformanceOverTimeSummary({
  data,
}: {
  data: PerformanceOverTimeType["summary"]
}) {
  return (
    <ul className="grid grid-cols-2 place-items-center gap-x-3">
      <li className="flex gap-x-2">
        <Badge
          style={{
            backgroundColor: "hsl(var(--chart-1))",
          }}
          className="size-12 aspect-square bg-chart-1"
          aria-hidden
        >
          <Eye className="size-full" />
        </Badge>
        <div className="shrink-0">
          <h3 className="text-sm text-muted-foreground leading-tight">
            Total Visitors
          </h3>
          <p className="text-2xl font-semibold">
            {data.totalVisitors.toLocaleString()}
          </p>
        </div>
      </li>
      <li className="flex gap-x-2">
        <Badge
          style={{
            backgroundColor: "hsl(var(--chart-2))",
          }}
          className="size-12 aspect-square bg-chart-2"
          aria-hidden
        >
          <RefreshCw className="size-full" />
        </Badge>
        <div>
          <h3 className="text-sm text-muted-foreground leading-tight line-clamp-1 break-all">
            Total Conversions
          </h3>
          <p className="text-2xl font-semibold">
            {data.totalConversions.toLocaleString()}
          </p>
        </div>
      </li>
    </ul>
  )
}
