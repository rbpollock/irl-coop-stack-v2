"use client"

import { Italic } from "lucide-react"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Toggle } from "@/components/ui/toggle"

export function ToggleSmall() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Toggle Small</CardTitle>
      </CardHeader>
      <CardContent className="flex justify-center items-center">
        <Toggle size="sm" aria-label="Toggle italic">
          <Italic />
        </Toggle>
      </CardContent>
    </Card>
  )
}
