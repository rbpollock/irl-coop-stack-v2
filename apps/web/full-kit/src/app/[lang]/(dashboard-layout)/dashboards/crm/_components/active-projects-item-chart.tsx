"use client"

import {
  Label,
  PolarAngleAxis,
  PolarRadiusAxis,
  RadialBar,
  RadialBarChart,
} from "recharts"

import { useRadius } from "@/hooks/use-radius"
import { ChartContainer } from "@/components/ui/chart"

export function ActiveProjectsItemChart({
  value,
  maxRating = 100,
  color = "hsl(var(--success))",
}: {
  value: number
  maxRating?: number
  color?: string
}) {
  const radius = useRadius()

  return (
    <ChartContainer config={{}} className="aspect-square h-16">
      <RadialBarChart
        accessibilityLayer
        data={[{ value }]}
        innerRadius={25}
        outerRadius="150%"
      >
        <PolarAngleAxis
          type="number"
          domain={[0, maxRating]}
          angleAxisId={0}
          tick={false}
        />
        <RadialBar
          background
          dataKey="value"
          cornerRadius={radius}
          fill={color}
        />
        <PolarRadiusAxis tick={false} tickLine={false} axisLine={false}>
          <Label
            content={({ viewBox }) => {
              if (viewBox && "cx" in viewBox && "cy" in viewBox) {
                return (
                  <text
                    x={viewBox.cx}
                    y={viewBox.cy}
                    textAnchor="middle"
                    dominantBaseline="middle"
                  >
                    <tspan
                      x={viewBox.cx}
                      y={(viewBox.cy || 0) + 2}
                      className="fill-foreground text-sm font-semibold"
                    >
                      {value}%
                    </tspan>
                  </text>
                )
              }
            }}
          />
        </PolarRadiusAxis>
      </RadialBarChart>
    </ChartContainer>
  )
}
