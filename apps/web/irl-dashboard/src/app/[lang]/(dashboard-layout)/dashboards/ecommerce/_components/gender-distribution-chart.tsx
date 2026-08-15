"use client"

import { Scatter, ScatterChart, XAxis, YAxis } from "recharts"

import type { ComponentProps } from "react"
import type { ScatterPointItem } from "recharts/types/cartesian/Scatter"
import type { GenderDistributionType } from "../../analytics/types"

import { formatPercent } from "@/lib/utils"

import { useIsRtl } from "@/hooks/use-is-rtl"
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from "@/components/ui/chart"

// Function to normalize values to proportional sizes
const getNormalizedSize = (value: number, min: number, max: number) => {
  const minSize = 25 // Minimum bubble radius
  const maxSize = 45 // Maximum bubble radius
  return minSize + ((value - min) / (max - min)) * (maxSize - minSize)
}

function ModifiedChartTooltipContent(
  props: ComponentProps<typeof ChartTooltipContent>
) {
  if (!props.payload || props.payload.length === 0) return null

  const item = props.payload[0]

  return (
    <ChartTooltipContent
      {...props}
      payload={[
        {
          ...item,
          name: item.payload.name,
          value: item.payload.value,
        },
      ]}
    />
  )
}

export function GenderDistributionChart({
  data,
}: {
  data: GenderDistributionType[]
}) {
  const isRtl = useIsRtl()

  const values = data.map((item) => item.value)
  const minValue = Math.min(...values)
  const maxValue = Math.max(...values)

  return (
    <ChartContainer
      config={{}}
      className="aspect-square max-w-56 h-full w-full mx-auto"
    >
      <ScatterChart margin={{ top: 0, right: 0, bottom: 0, left: 0 }}>
        <ChartTooltip
          cursor={false}
          content={<ModifiedChartTooltipContent />}
        />
        <XAxis
          reversed={isRtl}
          type="number"
          dataKey="x"
          domain={[0, 5]}
          hide
        />
        <YAxis type="number" dataKey="y" domain={[0, 5]} hide />
        <Scatter
          name="Gender Distribution"
          data={data}
          isAnimationActive
          shape={(props: ScatterPointItem) => {
            const { cx, cy, payload } = props
            const radius = getNormalizedSize(payload.value, minValue, maxValue)
            const percentage = formatPercent(payload.percentage)

            return (
              <g>
                <circle
                  cx={cx}
                  cy={cy}
                  r={radius}
                  fill={payload.fill}
                  opacity={0.8}
                />
                <text
                  x={cx}
                  y={(cy || 0) - 4}
                  textAnchor="middle"
                  dominantBaseline="middle"
                  className="fill-white text-xs font-semibold"
                >
                  {payload.name}
                </text>
                <text
                  x={cx}
                  y={(cy || 0) + 8.5}
                  textAnchor="middle"
                  dominantBaseline="middle"
                  className="fill-white text-base font-semibold"
                >
                  {percentage}
                </text>
              </g>
            )
          }}
        />
      </ScatterChart>
    </ChartContainer>
  )
}
