"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"

export function BasicPopover() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Basic Popover</CardTitle>
      </CardHeader>
      <CardContent className="flex justify-center items-center">
        <Popover>
          <PopoverTrigger>Open</PopoverTrigger>
          <PopoverContent>Place content for the popover here.</PopoverContent>
        </Popover>
      </CardContent>
    </Card>
  )
}
