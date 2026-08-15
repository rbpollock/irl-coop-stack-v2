"use client"

import {
  Label,
  PolarAngleAxis,
  PolarRadiusAxis,
  RadialBar,
  RadialBarChart,
} from "recharts"

import type { CustomerSatisfactionType } from "../types"

import { ratingToPercentage } from "@/lib/utils"

import { useRadius } from "@/hooks/use-radius"
import { ChartContainer } from "@/components/ui/chart"

export function CustomerSatisfactionChart({
  data,
}: {
  data: CustomerSatisfactionType["summary"]
}) {
  const radius = useRadius()

  const maxRating = 5

  return (
    <ChartContainer config={{}} className="aspect-square h-[12.5rem] md:w-2/5">
      <RadialBarChart
        accessibilityLayer
        data={[data]}
        endAngle={360}
        innerRadius={80}
        outerRadius={150}
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
          fill="hsl(var(--primary))"
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
                      y={viewBox.cy}
                      className="fill-foreground text-4xl font-semibold"
                    >
                      {data.value} / 5
                    </tspan>
                    <tspan
                      x={viewBox.cx}
                      y={(viewBox.cy || 0) + 24}
                      className="text-sm fill-muted-foreground"
                    >
                      {ratingToPercentage(data.value, maxRating)} Satisfied
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
