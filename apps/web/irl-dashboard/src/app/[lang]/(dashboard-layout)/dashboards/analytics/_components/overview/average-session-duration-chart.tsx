"use client"

import { Bar, BarChart, CartesianGrid, XAxis } from "recharts"

import type { ChartConfig } from "@/components/ui/chart"
import type { ComponentProps } from "react"
import type { OverviewType } from "../../types"

import { formatDuration } from "@/lib/utils"

import { useIsRtl } from "@/hooks/use-is-rtl"
import { useRadius } from "@/hooks/use-radius"
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
        value: formatDuration(Number(item.value)),
      }))}
    />
  )
}

const chartConfig = {
  value: {
    label: "Duration",
  },
} satisfies ChartConfig

export function AverageSessionDurationChart({
  data,
}: {
  data: OverviewType["averageSessionDuration"]["perMonth"]
}) {
  const isRtl = useIsRtl()
  const radius = useRadius()

  return (
    <ChartContainer
      config={chartConfig}
      className="h-32 w-full rounded-b-md overflow-hidden"
    >
      <BarChart accessibilityLayer data={data}>
        <CartesianGrid vertical={false} />
        <ChartTooltip
          cursor={false}
          content={<ModifiedChartTooltipContent />}
        />
        <XAxis reversed={isRtl} dataKey="month" hide />
        <Bar dataKey="value" barSize={44} radius={radius} />
      </BarChart>
    </ChartContainer>
  )
}
