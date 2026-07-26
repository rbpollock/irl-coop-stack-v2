"use client"

import { RadialBar, RadialBarChart } from "recharts"

import type { ChartConfig } from "@/components/ui/chart"
import type { TrafficSourcesType } from "../types"

import { useRadius } from "@/hooks/use-radius"
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from "@/components/ui/chart"

const chartConfig = {
  visitors: {
    label: "Visitors",
  },
} satisfies ChartConfig

export function TrafficSourcesChart({
  data,
}: {
  data: TrafficSourcesType["sources"]
}) {
  const radius = useRadius()

  return (
    <ChartContainer config={chartConfig} className="aspect-square h-52 mx-auto">
      <RadialBarChart data={data} innerRadius={30} outerRadius={110}>
        <ChartTooltip
          cursor={false}
          content={<ChartTooltipContent hideLabel />}
        />
        <RadialBar dataKey="visitors" background cornerRadius={radius} />
      </RadialBarChart>
    </ChartContainer>
  )
}
