"use client"

import { useState } from "react"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { DatePicker as DatePickerComponent } from "@/components/ui/date-picker"

export function DatePicker() {
  const [date, setDate] = useState<Date | undefined>()

  return (
    <Card>
      <CardHeader>
        <CardTitle>Date Picker</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-2">
        <DatePickerComponent value={date} onValueChange={setDate} />
      </CardContent>
    </Card>
  )
}
