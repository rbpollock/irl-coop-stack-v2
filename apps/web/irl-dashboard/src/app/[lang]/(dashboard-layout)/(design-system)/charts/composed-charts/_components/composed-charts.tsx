"use client"

import {
  Area,
  Bar,
  CartesianGrid,
  ComposedChart,
  Line,
  XAxis,
  YAxis,
} from "recharts"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from "@/components/ui/chart"

const composedChartsData = [
  { name: "Page A", uv: 590, pv: 800, amt: 1400 },
  { name: "Page B", uv: 868, pv: 967, amt: 1506 },
  { name: "Page C", uv: 1397, pv: 1098, amt: 989 },
  { name: "Page D", uv: 1480, pv: 1200, amt: 1228 },
  { name: "Page E", uv: 1520, pv: 1108, amt: 1100 },
  { name: "Page F", uv: 1400, pv: 680, amt: 1700 },
]

export function ComposedCharts() {
  return (
    <section className="conatiner grid gap-4 p-4">
      <Card>
        <CardHeader>
          <CardTitle>Bar Area Composed Chart</CardTitle>
        </CardHeader>
        <CardContent>
          <ChartContainer config={{}} className="w-full">
            <ComposedChart data={composedChartsData}>
              <CartesianGrid stroke="#f5f5f5" />
              <XAxis dataKey="name" />
              <YAxis />
              <ChartTooltip content={<ChartTooltipContent />} />
              <Area
                type="monotone"
                dataKey="amt"
                fill="hsl(var(--chart-1))"
                stroke="hsl(var(--chart-1))"
              />
              <Bar dataKey="pv" barSize={20} fill="hsl(var(--chart-2))" />
              <Line type="monotone" dataKey="uv" stroke="hsl(var(--chart-3))" />
            </ComposedChart>
          </ChartContainer>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Same Data Composed Chart</CardTitle>
        </CardHeader>
        <CardContent>
          <ChartContainer config={{}} className="w-full">
            <ComposedChart data={composedChartsData}>
              <CartesianGrid stroke="#f5f5f5" />
              <XAxis dataKey="name" />
              <YAxis />
              <ChartTooltip content={<ChartTooltipContent />} />
              <Area
                type="monotone"
                dataKey="amt"
                fill="hsl(var(--chart-1))"
                stroke="hsl(var(--chart-1))"
              />
              <Bar dataKey="amt" barSize={20} fill="hsl(var(--chart-2))" />
              <Line
                type="monotone"
                dataKey="amt"
                stroke="hsl(var(--chart-3))"
              />
            </ComposedChart>
          </ChartContainer>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Vertical Composed Chart</CardTitle>
        </CardHeader>
        <CardContent>
          <ChartContainer config={{}} className="w-full">
            <ComposedChart layout="vertical" data={composedChartsData}>
              <CartesianGrid stroke="#f5f5f5" />
              <XAxis type="number" />
              <YAxis dataKey="name" type="category" />
              <ChartTooltip content={<ChartTooltipContent />} />
              <Area
                dataKey="amt"
                fill="hsl(var(--chart-1))"
                stroke="hsl(var(--chart-1))"
              />
              <Bar dataKey="pv" barSize={20} fill="hsl(var(--chart-2))" />
              <Line dataKey="uv" stroke="hsl(var(--chart-3))" />
            </ComposedChart>
          </ChartContainer>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Composed Chart With Axis Labels</CardTitle>
        </CardHeader>
        <CardContent>
          <ChartContainer config={{}} className="w-full">
            <ComposedChart data={composedChartsData}>
              <CartesianGrid stroke="#f5f5f5" />
              <XAxis
                dataKey="name"
                label={{
                  value: "Pages",
                  position: "insideBottomRight",
                  offset: 0,
                }}
              />
              <YAxis
                label={{
                  value: "Index",
                  angle: -90,
                  position: "insideLeft",
                }}
              />
              <ChartTooltip content={<ChartTooltipContent />} />
              <Area
                type="monotone"
                dataKey="amt"
                fill="hsl(var(--chart-1))"
                stroke="hsl(var(--chart-1))"
              />
              <Bar dataKey="pv" barSize={20} fill="hsl(var(--chart-2))" />
              <Line type="monotone" dataKey="uv" stroke="hsl(var(--chart-3))" />
            </ComposedChart>
          </ChartContainer>
        </CardContent>
      </Card>
    </section>
  )
}
