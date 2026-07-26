"use client"

import { useState } from "react"

import type { DateRange } from "react-day-picker"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { DateRangePicker as DateRangePickerComponent } from "@/components/ui/date-range-picker"

export function DateRangePicker() {
  const [range, setRange] = useState<DateRange>()

  return (
    <Card>
      <CardHeader>
        <CardTitle>Date Range Picker</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-2">
        <DateRangePickerComponent value={range} onValueChange={setRange} />
      </CardContent>
    </Card>
  )
}
