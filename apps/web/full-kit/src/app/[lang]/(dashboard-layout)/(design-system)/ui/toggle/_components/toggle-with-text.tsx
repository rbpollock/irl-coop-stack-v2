"use client"

import { Italic } from "lucide-react"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Toggle } from "@/components/ui/toggle"

export function ToggleWithText() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Toggle with Text</CardTitle>
      </CardHeader>
      <CardContent className="flex justify-center items-center">
        <Toggle aria-label="Toggle italic">
          <Italic />
          Italic
        </Toggle>
      </CardContent>
    </Card>
  )
}
