"use client"

import { Bar, BarChart, XAxis, YAxis } from "recharts"

import type { RevenueBySourceType } from "../types"

import { useIsRtl } from "@/hooks/use-is-rtl"
import { useRadius } from "@/hooks/use-radius"
import { ChartContainer } from "@/components/ui/chart"

export function RevenueBySourceChart({
  data,
}: {
  data: RevenueBySourceType["sources"]
}) {
  const isRtl = useIsRtl()
  const radius = useRadius()

  const chartData = data.reduce((acc: { [key: string]: number }, source) => {
    acc[source.name.toLocaleLowerCase()] = source.value
    return acc
  }, {})

  return (
    <ChartContainer config={{}} className="h-4 w-full">
      <BarChart
        accessibilityLayer
        data={[chartData]}
        layout="vertical"
        margin={{ top: 0, right: 0, left: 0, bottom: 0 }}
      >
        <XAxis type="number" reversed={isRtl} hide />
        <YAxis type="category" hide />
        {data.map((item) => (
          <Bar
            key={item.name}
            dataKey={item.name.toLocaleLowerCase()}
            stackId="a"
            fill={item.fill}
            radius={radius}
          />
        ))}
      </BarChart>
    </ChartContainer>
  )
}
