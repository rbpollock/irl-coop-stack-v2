"use client"

import { Bold } from "lucide-react"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Toggle } from "@/components/ui/toggle"

export function BasicToggle() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Basic Toggle</CardTitle>
      </CardHeader>
      <CardContent className="flex justify-center items-center">
        <Toggle aria-label="Toggle italic">
          <Bold className="h-4 w-4" />
        </Toggle>
      </CardContent>
    </Card>
  )
}
