"use client"

import { Underline } from "lucide-react"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Toggle } from "@/components/ui/toggle"

export function ToggleDisabled() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Toggle Disabled</CardTitle>
      </CardHeader>
      <CardContent className="flex justify-center items-center">
        <Toggle aria-label="Toggle italic" disabled>
          <Underline className="h-4 w-4" />
        </Toggle>
      </CardContent>
    </Card>
  )
}
