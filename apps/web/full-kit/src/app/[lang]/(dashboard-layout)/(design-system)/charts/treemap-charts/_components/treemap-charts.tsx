"use client"

import { Treemap } from "recharts"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from "@/components/ui/chart"

const treemapChartsData = [
  { name: "axis", size: 2100 },
  { name: "controls", size: 1600 },
  { name: "data", size: 1800 },
  { name: "layouts", size: 1900 },
  { name: "scales", size: 2100 },
  { name: "util", size: 2200 },
]

export function TreemapCharts() {
  return (
    <section className="conatiner grid gap-4 p-4">
      <Card>
        <CardHeader>
          <CardTitle>Simple Tree Map</CardTitle>
        </CardHeader>
        <CardContent>
          <ChartContainer config={{}} className="w-full">
            <Treemap
              data={treemapChartsData}
              dataKey="size"
              aspectRatio={4 / 3}
              stroke="#fff"
              fill="hsl(var(--chart-1))"
            >
              <ChartTooltip content={<ChartTooltipContent />} />
            </Treemap>
          </ChartContainer>
        </CardContent>
      </Card>
    </section>
  )
}
