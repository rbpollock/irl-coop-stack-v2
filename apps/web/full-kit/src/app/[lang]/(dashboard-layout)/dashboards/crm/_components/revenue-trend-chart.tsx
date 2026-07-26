"use client"

import { Bar, BarChart, CartesianGrid, XAxis } from "recharts"

import type { ChartConfig } from "@/components/ui/chart"
import type { ComponentProps } from "react"
import type { RevenueTrendType } from "../types"

import { formatCurrency } from "@/lib/utils"

import { useIsRtl } from "@/hooks/use-is-rtl"
import { useRadius } from "@/hooks/use-radius"
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from "@/components/ui/chart"

const chartConfig = {
  revenue: {
    label: "Revenue",
  },
} satisfies ChartConfig

function ModifiedChartTooltipContent(
  props: ComponentProps<typeof ChartTooltipContent>
) {
  if (!props.payload || props.payload.length === 0) return null

  return (
    <ChartTooltipContent
      {...props}
      payload={props.payload.map((item) => ({
        ...item,
        value: formatCurrency(Number(item.value)),
      }))}
    />
  )
}

export function RevenueTrendChart({
  data,
}: {
  data: RevenueTrendType["revenueTrends"]
}) {
  const radius = useRadius()
  const isRtl = useIsRtl()

  return (
    <ChartContainer config={chartConfig} className="aspect-auto grow w-full">
      <BarChart
        accessibilityLayer
        data={data}
        margin={{
          left: 0,
          right: 0,
        }}
      >
        <CartesianGrid vertical={false} />
        <XAxis
          reversed={isRtl}
          dataKey="month"
          tickLine={false}
          axisLine={false}
          hide
        />
        <ChartTooltip content={<ModifiedChartTooltipContent hideIndicator />} />
        <Bar dataKey="revenue" fill="hsl(var(--chart-2))" radius={radius} />
      </BarChart>
    </ChartContainer>
  )
}
