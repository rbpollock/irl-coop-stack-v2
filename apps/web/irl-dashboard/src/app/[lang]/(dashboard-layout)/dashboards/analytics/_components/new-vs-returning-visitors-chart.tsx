"use client"

import { Bar, BarChart, XAxis, YAxis } from "recharts"

import type { NewVsReturningVisitorsType } from "../types"

import { useIsRtl } from "@/hooks/use-is-rtl"
import { useRadius } from "@/hooks/use-radius"
import { ChartContainer } from "@/components/ui/chart"

export function NewVsReturningVisitorsChart({
  data,
}: {
  data: NewVsReturningVisitorsType["visitors"]
}) {
  const radius = useRadius()
  const isRtl = useIsRtl()

  // Transform `data` into an array format suitable for Recharts
  const chartData = [{ new: data.new.value, returning: data.returning.value }]

  return (
    <ChartContainer config={{}} className="h-4 w-full">
      <BarChart
        data={chartData}
        layout="vertical"
        margin={{ top: 0, right: 0, left: 0, bottom: 0 }}
      >
        <XAxis
          type="number"
          reversed={isRtl}
          domain={["dataMin", "dataMax"]}
          hide
        />
        <YAxis type="category" hide />
        <Bar dataKey="new" stackId="a" fill={data.new.fill} radius={radius} />
        <Bar
          dataKey="returning"
          stackId="a"
          fill={data.returning.fill}
          radius={radius}
        />
      </BarChart>
    </ChartContainer>
  )
}
