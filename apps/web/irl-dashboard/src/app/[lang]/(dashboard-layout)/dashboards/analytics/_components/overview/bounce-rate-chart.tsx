"use client"

import { CartesianGrid, Line, LineChart, XAxis } from "recharts"

import type { ChartConfig } from "@/components/ui/chart"
import type { ComponentProps } from "react"
import type { OverviewType } from "../../types"

import { formatPercent } from "@/lib/utils"

import { useIsRtl } from "@/hooks/use-is-rtl"
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from "@/components/ui/chart"

function ModifiedChartTooltipContent(
  props: ComponentProps<typeof ChartTooltipContent>
) {
  if (!props.payload || props.payload.length === 0) return null

  return (
    <ChartTooltipContent
      {...props}
      payload={props.payload.map((item) => ({
        ...item,
        value: formatPercent(Number(item.value)),
      }))}
    />
  )
}

const chartConfig = {
  value: {
    label: "Rate",
  },
} satisfies ChartConfig

export function BounceRateChart({
  data,
}: {
  data: OverviewType["bounceRate"]["perMonth"]
}) {
  const isRtl = useIsRtl()

  return (
    <ChartContainer
      config={chartConfig}
      className="h-32 w-full rounded-b-md overflow-hidden"
    >
      <LineChart
        accessibilityLayer
        data={data}
        margin={{
          left: 0,
          right: 0,
        }}
      >
        <CartesianGrid vertical={false} />
        <XAxis reversed={isRtl} dataKey="month" hide />
        <ChartTooltip
          cursor={false}
          content={<ModifiedChartTooltipContent />}
        />
        <Line
          dataKey="value"
          type="linear"
          stroke="hsl(var(--chart-3))"
          strokeWidth={2}
          dot={false}
        />
      </LineChart>
    </ChartContainer>
  )
}
