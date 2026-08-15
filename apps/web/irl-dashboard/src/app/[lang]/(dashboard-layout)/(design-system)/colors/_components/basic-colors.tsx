import { basicColorsData } from "../_data/basic-colors"

import { cn } from "@/lib/utils"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

export function BasicColors() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Basic Colors</CardTitle>
      </CardHeader>
      <CardContent>
        <BasicColorsList />
      </CardContent>
    </Card>
  )
}

function BasicColorsList() {
  return (
    <ul className="grid gap-4">
      {basicColorsData.map((color) => (
        <BasicColorsItem key={color.label} data={color} />
      ))}
    </ul>
  )
}

function BasicColorsItem({ data }: { data: (typeof basicColorsData)[number] }) {
  return (
    <li className="flex items-center gap-x-2">
      <div className={cn("size-4 rounded-md", data.class)} />
      <span>{data.label}</span>
    </li>
  )
}
