"use client"

import { useState } from "react"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { DateTimePicker as DateTimePickerComponent } from "@/components/ui/date-time-picker"

export function DateTimePicker() {
  const [dateTime, setDateTime] = useState<Date | undefined>()

  return (
    <Card>
      <CardHeader>
        <CardTitle>Date Time Picker</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-2">
        <DateTimePickerComponent value={dateTime} onValueChange={setDateTime} />
      </CardContent>
    </Card>
  )
}
