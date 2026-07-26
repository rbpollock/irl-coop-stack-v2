"use client"

import { Italic } from "lucide-react"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Toggle } from "@/components/ui/toggle"

export function ToggleOutline() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Toggle Outline</CardTitle>
      </CardHeader>
      <CardContent className="flex justify-center items-center">
        <Toggle variant="outline" aria-label="Toggle italic">
          <Italic />
        </Toggle>
      </CardContent>
    </Card>
  )
}
