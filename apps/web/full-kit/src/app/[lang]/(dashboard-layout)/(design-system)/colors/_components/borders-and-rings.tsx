import { bordersAndRingsData } from "../_data/borders-and-rings"

import { cn } from "@/lib/utils"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

export function BordersAndRings() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Borders and Rings</CardTitle>
      </CardHeader>
      <CardContent>
        <BordersAndRingsList />
      </CardContent>
    </Card>
  )
}

function BordersAndRingsList() {
  return (
    <ul className="grid gap-4">
      {bordersAndRingsData.map((color) => (
        <BordersAndRingsItem key={color.label} data={color} />
      ))}
    </ul>
  )
}

function BordersAndRingsItem({
  data,
}: {
  data: (typeof bordersAndRingsData)[number]
}) {
  return (
    <li className="flex items-center gap-x-2">
      <div className={cn("size-4 rounded-md", data.class)} />
      <span>{data.label}</span>
    </li>
  )
}
