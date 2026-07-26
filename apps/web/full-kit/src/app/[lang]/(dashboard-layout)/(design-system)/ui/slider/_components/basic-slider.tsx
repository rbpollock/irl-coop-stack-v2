"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Slider } from "@/components/ui/slider"

export function BasicSlider() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Basic Slider</CardTitle>
      </CardHeader>
      <CardContent className="flex justify-center items-center">
        <Slider defaultValue={[33]} max={100} step={1} />
      </CardContent>
    </Card>
  )
}
