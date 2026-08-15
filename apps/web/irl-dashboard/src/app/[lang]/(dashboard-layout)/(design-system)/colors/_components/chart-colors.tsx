import { chartColorsData } from "../_data/chart-colors"

import { cn } from "@/lib/utils"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

export function ChartColors() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Chart Colors</CardTitle>
      </CardHeader>
      <CardContent>
        <ChartColorsList />
      </CardContent>
    </Card>
  )
}

function ChartColorsList() {
  return (
    <ul className="grid gap-4">
      {chartColorsData.map((color) => (
        <ChartColorsItem key={color.label} data={color} />
      ))}
    </ul>
  )
}

function ChartColorsItem({ data }: { data: (typeof chartColorsData)[number] }) {
  return (
    <li className="flex items-center gap-x-2">
      <div className={cn("size-4 rounded-md", data.class)} />
      <span>{data.label}</span>
    </li>
  )
}
