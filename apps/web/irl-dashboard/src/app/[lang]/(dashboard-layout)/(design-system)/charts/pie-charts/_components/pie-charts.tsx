"use client"

import { Cell, Pie, PieChart } from "recharts"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from "@/components/ui/chart"

const pieChartsData = [
  { name: "Group A", value: 400 },
  { name: "Group B", value: 300 },
  { name: "Group C", value: 300 },
  { name: "Group D", value: 200 },
  { name: "Group E", value: 278 },
  { name: "Group F", value: 189 },
]

export function PieCharts() {
  return (
    <section className="conatiner grid gap-4 p-4">
      <Card>
        <CardHeader>
          <CardTitle>Two Level Pie Chart</CardTitle>
        </CardHeader>
        <CardContent>
          <ChartContainer config={{}} className="w-full">
            <PieChart>
              <Pie
                data={pieChartsData}
                dataKey="value"
                nameKey="name"
                cx="50%"
                cy="50%"
                outerRadius={50}
                fill="hsl(var(--chart-1))"
              />
              <Pie
                data={pieChartsData}
                dataKey="value"
                nameKey="name"
                cx="50%"
                cy="50%"
                innerRadius={60}
                outerRadius={80}
                fill="hsl(var(--chart-2))"
                label
              />
              <ChartTooltip content={<ChartTooltipContent />} />
            </PieChart>
          </ChartContainer>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Straight Angle Pie Chart</CardTitle>
        </CardHeader>
        <CardContent>
          <ChartContainer config={{}} className="w-full">
            <PieChart>
              <Pie
                data={pieChartsData}
                dataKey="value"
                nameKey="name"
                cx="50%"
                cy="50%"
                startAngle={180}
                endAngle={0}
                innerRadius={60}
                outerRadius={80}
                fill="hsl(var(--chart-1))"
                label
              />
              <ChartTooltip content={<ChartTooltipContent />} />
            </PieChart>
          </ChartContainer>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Two Simple Pie Chart</CardTitle>
        </CardHeader>
        <CardContent>
          <ChartContainer config={{}} className="w-full">
            <PieChart>
              <Pie
                data={pieChartsData}
                dataKey="value"
                nameKey="name"
                cx="50%"
                cy="50%"
                outerRadius={50}
                fill="hsl(var(--chart-1))"
              />
              <Pie
                data={pieChartsData}
                dataKey="value"
                nameKey="name"
                cx="50%"
                cy="50%"
                innerRadius={60}
                outerRadius={80}
                fill="hsl(var(--chart-2))"
                label
              />
              <ChartTooltip content={<ChartTooltipContent />} />
            </PieChart>
          </ChartContainer>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Pie Chart With Customized Label</CardTitle>
        </CardHeader>
        <CardContent>
          <ChartContainer config={{}} className="w-full">
            <PieChart>
              <Pie
                data={pieChartsData}
                cx="50%"
                cy="50%"
                labelLine={false}
                outerRadius={80}
                fill="hsl(var(--chart-1))"
                dataKey="value"
              >
                {pieChartsData.map((_, index) => (
                  <Cell
                    key={`cell-${index}`}
                    fill={`hsl(var(--chart-${(index % 5) + 1}))`}
                  />
                ))}
              </Pie>
              <ChartTooltip content={<ChartTooltipContent />} />
            </PieChart>
          </ChartContainer>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Pie Chart With Padding Angle</CardTitle>
        </CardHeader>
        <CardContent>
          <ChartContainer config={{}} className="w-full">
            <PieChart>
              <Pie
                data={pieChartsData}
                cx="50%"
                cy="50%"
                innerRadius={60}
                outerRadius={80}
                fill="hsl(var(--chart-1))"
                paddingAngle={5}
                dataKey="value"
              >
                {pieChartsData.map((_, index) => (
                  <Cell
                    key={`cell-${index}`}
                    fill={`hsl(var(--chart-${(index % 5) + 1}))`}
                  />
                ))}
              </Pie>
              <ChartTooltip content={<ChartTooltipContent />} />
            </PieChart>
          </ChartContainer>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Pie Chart With Needle</CardTitle>
        </CardHeader>
        <CardContent>
          <ChartContainer config={{}} className="w-full">
            <PieChart>
              <Pie
                data={[
                  { name: "A", value: 80 },
                  { name: "B", value: 20 },
                ]}
                cx="50%"
                cy="50%"
                startAngle={180}
                endAngle={0}
                innerRadius={60}
                outerRadius={80}
                fill="hsl(var(--chart-1))"
                dataKey="value"
              >
                {pieChartsData.map((_, index) => (
                  <Cell
                    key={`cell-${index}`}
                    fill={`hsl(var(--chart-${(index % 2) + 1}))`}
                  />
                ))}
              </Pie>
              {/* <Customized component={NeedleComponent} /> */}
            </PieChart>
          </ChartContainer>
        </CardContent>
      </Card>
    </section>
  )
}
