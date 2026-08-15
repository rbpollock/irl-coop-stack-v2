"use client"

import { CartesianGrid, Line, LineChart, XAxis, YAxis } from "recharts"

import type { PerformanceOverTimeType } from "../types"

import { useIsRtl } from "@/hooks/use-is-rtl"
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from "@/components/ui/chart"

export function PerformanceOverTimeChart({
  data,
}: {
  data: PerformanceOverTimeType["performance"]
}) {
  const isRtl = useIsRtl()

  return (
    <ChartContainer config={{}} className="aspect-auto h-full w-full">
      <LineChart
        accessibilityLayer
        data={data}
        margin={{
          left: 12,
          right: 12,
        }}
      >
        <CartesianGrid vertical={false} />
        <XAxis
          reversed={isRtl}
          dataKey="month"
          tickLine={false}
          axisLine={false}
          tickMargin={8}
          tickFormatter={(value) => value.slice(0, 3)}
        />
        <YAxis yAxisId="left" hide />
        <YAxis yAxisId="right" orientation="right" hide />
        <ChartTooltip cursor={false} content={<ChartTooltipContent />} />
        <Line
          dataKey="visitors"
          yAxisId="left"
          type="linear"
          stroke="hsl(var(--chart-1))"
          strokeWidth={2}
          dot={false}
        />
        <Line
          dataKey="conversions"
          yAxisId="right"
          type="linear"
          stroke="hsl(var(--chart-2))"
          strokeWidth={2}
          dot={false}
        />
      </LineChart>
    </ChartContainer>
  )
}
