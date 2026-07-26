"use client"

import {
  CartesianGrid,
  Cell,
  LabelList,
  Scatter,
  ScatterChart,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from "@/components/ui/chart"

const scatterChartsData = [
  { x: 100, y: 200, z: 200 },
  { x: 120, y: 100, z: 260 },
  { x: 170, y: 300, z: 400 },
  { x: 140, y: 250, z: 280 },
  { x: 150, y: 400, z: 500 },
  { x: 110, y: 280, z: 200 },
]

export function ScatterCharts() {
  return (
    <section className="conatiner grid gap-4 p-4">
      <Card>
        <CardHeader>
          <CardTitle>Basic Scatter Chart</CardTitle>
        </CardHeader>
        <CardContent>
          <ChartContainer config={{}} className="w-full">
            <ScatterChart>
              <CartesianGrid />
              <XAxis type="number" dataKey="x" name="stature" unit="cm" />
              <YAxis type="number" dataKey="y" name="weight" unit="kg" />
              <ChartTooltip
                cursor={{ strokeDasharray: "3 3" }}
                content={<ChartTooltipContent />}
              />
              <Scatter
                name="A school"
                data={scatterChartsData}
                fill="hsl(var(--chart-1))"
              />
            </ScatterChart>
          </ChartContainer>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Three Dim Scatter Chart</CardTitle>
        </CardHeader>
        <CardContent>
          <ChartContainer config={{}} className="w-full">
            <ScatterChart>
              <CartesianGrid />
              <XAxis type="number" dataKey="x" name="stature" unit="cm" />
              <YAxis type="number" dataKey="y" name="weight" unit="kg" />
              <ZAxis
                type="number"
                dataKey="z"
                range={[60, 400]}
                name="score"
                unit="km"
              />
              <ChartTooltip
                cursor={{ strokeDasharray: "3 3" }}
                content={<ChartTooltipContent />}
              />
              <Scatter
                name="A school"
                data={scatterChartsData}
                fill="hsl(var(--chart-1))"
              />
            </ScatterChart>
          </ChartContainer>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Joint Line Scatter Chart</CardTitle>
        </CardHeader>
        <CardContent>
          <ChartContainer config={{}} className="w-full">
            <ScatterChart>
              <CartesianGrid />
              <XAxis type="number" dataKey="x" name="stature" unit="cm" />
              <YAxis type="number" dataKey="y" name="weight" unit="kg" />
              <ChartTooltip
                cursor={{ strokeDasharray: "3 3" }}
                content={<ChartTooltipContent />}
              />
              <Scatter
                name="A school"
                data={scatterChartsData}
                fill="hsl(var(--chart-1))"
                line
                shape="cross"
              />
            </ScatterChart>
          </ChartContainer>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Bubble Chart</CardTitle>
        </CardHeader>
        <CardContent>
          <ChartContainer config={{}} className="w-full">
            <ScatterChart>
              <CartesianGrid />
              <XAxis type="number" dataKey="x" name="stature" unit="cm" />
              <YAxis type="number" dataKey="y" name="weight" unit="kg" />
              <ZAxis
                type="number"
                dataKey="z"
                range={[60, 400]}
                name="score"
                unit="km"
              />
              <ChartTooltip
                cursor={{ strokeDasharray: "3 3" }}
                content={<ChartTooltipContent />}
              />
              <Scatter
                name="A school"
                data={scatterChartsData}
                fill="hsl(var(--chart-1))"
                shape="circle"
              />
            </ScatterChart>
          </ChartContainer>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Scatter Chart With Labels</CardTitle>
        </CardHeader>
        <CardContent>
          <ChartContainer config={{}} className="w-full">
            <ScatterChart>
              <CartesianGrid />
              <XAxis type="number" dataKey="x" name="stature" unit="cm" />
              <YAxis type="number" dataKey="y" name="weight" unit="kg" />
              <ChartTooltip
                cursor={{ strokeDasharray: "3 3" }}
                content={<ChartTooltipContent />}
              />
              <Scatter
                name="A school"
                data={scatterChartsData}
                fill="hsl(var(--chart-1))"
              >
                <LabelList dataKey="x" />
              </Scatter>
            </ScatterChart>
          </ChartContainer>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Multiple YAxes Scatter Chart</CardTitle>
        </CardHeader>
        <CardContent>
          <ChartContainer config={{}} className="w-full">
            <ScatterChart>
              <CartesianGrid />
              <XAxis type="number" dataKey="x" name="stature" unit="cm" />
              <YAxis
                yAxisId="left"
                type="number"
                dataKey="y"
                name="weight"
                unit="kg"
                stroke="hsl(var(--chart-1))"
              />
              <YAxis
                yAxisId="right"
                type="number"
                dataKey="y"
                name="weight"
                unit="kg"
                orientation="right"
                stroke="hsl(var(--chart-2))"
              />
              <ChartTooltip
                cursor={{ strokeDasharray: "3 3" }}
                content={<ChartTooltipContent />}
              />
              <Scatter
                yAxisId="left"
                name="A school"
                data={scatterChartsData}
                fill="hsl(var(--chart-1))"
              />
              <Scatter
                yAxisId="right"
                name="A school"
                data={scatterChartsData}
                fill="hsl(var(--chart-2))"
              />
            </ScatterChart>
          </ChartContainer>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Scatter Chart With Cells</CardTitle>
        </CardHeader>
        <CardContent>
          <ChartContainer config={{}} className="w-full">
            <ScatterChart>
              <CartesianGrid />
              <XAxis type="number" dataKey="x" name="stature" unit="cm" />
              <YAxis type="number" dataKey="y" name="weight" unit="kg" />
              <ChartTooltip
                cursor={{ strokeDasharray: "3 3" }}
                content={<ChartTooltipContent />}
              />
              <Scatter name="A school" data={scatterChartsData}>
                {scatterChartsData.map((_, index) => (
                  <Cell
                    key={`cell-${index}`}
                    fill={`hsl(var(--chart-${(index % 5) + 1}))`}
                  />
                ))}
              </Scatter>
            </ScatterChart>
          </ChartContainer>
        </CardContent>
      </Card>
    </section>
  )
}
