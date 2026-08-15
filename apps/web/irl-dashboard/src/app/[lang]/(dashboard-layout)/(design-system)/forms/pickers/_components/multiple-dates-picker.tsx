"use client"

import { useState } from "react"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { MultipleDatesPicker as MultipleDatesPickerComponent } from "@/components/ui/multiple-date-picker"

export function MultipleDatesPicker() {
  const [dates, setDates] = useState<Date[] | undefined>([])

  return (
    <Card>
      <CardHeader>
        <CardTitle>Multiple Dates Picker</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-2">
        <MultipleDatesPickerComponent value={dates} onValueChange={setDates} />
      </CardContent>
    </Card>
  )
}
