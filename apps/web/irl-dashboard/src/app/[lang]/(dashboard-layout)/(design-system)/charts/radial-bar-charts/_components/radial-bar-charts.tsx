"use client"

import { RadialBar, RadialBarChart } from "recharts"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  ChartContainer,
  ChartLegend,
  ChartTooltip,
  ChartTooltipContent,
} from "@/components/ui/chart"

const radialBarChartsData = [
  { name: "18-24", uv: 31.47, pv: 2400, fill: "hsl(var(--chart-1))" },
  { name: "25-29", uv: 26.69, pv: 4567, fill: "hsl(var(--chart-2))" },
  { name: "30-34", uv: 15.69, pv: 1398, fill: "hsl(var(--chart-3))" },
  { name: "35-39", uv: 8.22, pv: 9800, fill: "hsl(var(--chart-4))" },
]

export function RadialBarCharts() {
  return (
    <section className="conatiner grid gap-4 p-4">
      <Card>
        <CardHeader>
          <CardTitle>Simple Radial Bar Chart</CardTitle>
        </CardHeader>
        <CardContent>
          <ChartContainer config={{}} className="w-full">
            <RadialBarChart
              cx="50%"
              cy="50%"
              innerRadius="10%"
              outerRadius="80%"
              barSize={10}
              data={radialBarChartsData}
            >
              <RadialBar
                label={{ position: "insideStart", fill: "#fff" }}
                background
                dataKey="uv"
              />
              <ChartLegend
                iconSize={10}
                layout="vertical"
                verticalAlign="middle"
                align="right"
              />
              <ChartTooltip content={<ChartTooltipContent />} />
            </RadialBarChart>
          </ChartContainer>
        </CardContent>
      </Card>
    </section>
  )
}
