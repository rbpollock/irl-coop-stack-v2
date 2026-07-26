"use client"

import { Area, AreaChart, CartesianGrid, XAxis } from "recharts"

import type { ConversionFunnelType } from "../types"

import { useIsRtl } from "@/hooks/use-is-rtl"
import { ChartContainer } from "@/components/ui/chart"

export function ConversionFunnelChart({
  data,
}: {
  data: ConversionFunnelType["funnelSteps"]
}) {
  const isRtl = useIsRtl()

  return (
    <ChartContainer config={{}} className="aspect-video h-40 w-full">
      <AreaChart
        accessibilityLayer
        data={data}
        margin={{
          left: 0,
          right: 0,
        }}
      >
        <CartesianGrid vertical={false} />
        <XAxis reversed={isRtl} dataKey="name" hide />
        <Area
          dataKey="value"
          type="bump"
          activeDot={false}
          fill="hsl(var(--chart-2))"
          fillOpacity={0.4}
          stroke="hsl(var(--chart-2))"
        />
      </AreaChart>
    </ChartContainer>
  )
}
