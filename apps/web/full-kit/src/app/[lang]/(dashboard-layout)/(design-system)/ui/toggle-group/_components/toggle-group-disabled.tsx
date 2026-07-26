"use client"

import { Bold, Italic, Underline } from "lucide-react"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"

export function ToggleGroupDisabled() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Toggle Group Disabled</CardTitle>
      </CardHeader>
      <CardContent className="flex justify-center items-center">
        <ToggleGroup type="multiple" disabled>
          <ToggleGroupItem value="bold" aria-label="Toggle bold">
            <Bold className="h-4 w-4" />
          </ToggleGroupItem>
          <ToggleGroupItem value="italic" aria-label="Toggle italic">
            <Italic className="h-4 w-4" />
          </ToggleGroupItem>
          <ToggleGroupItem
            value="strikethrough"
            aria-label="Toggle strikethrough"
          >
            <Underline className="h-4 w-4" />
          </ToggleGroupItem>
        </ToggleGroup>
      </CardContent>
    </Card>
  )
}
