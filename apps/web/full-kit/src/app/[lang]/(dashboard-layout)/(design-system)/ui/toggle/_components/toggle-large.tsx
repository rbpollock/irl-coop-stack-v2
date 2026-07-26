"use client"

import { Italic } from "lucide-react"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Toggle } from "@/components/ui/toggle"

export function ToggleLarge() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Toggle Large</CardTitle>
      </CardHeader>
      <CardContent className="flex justify-center items-center">
        <Toggle size="lg" aria-label="Toggle italic">
          <Italic />
        </Toggle>
      </CardContent>
    </Card>
  )
}
