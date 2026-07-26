"use client"

import { useState } from "react"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { TimePicker as TimePickerComponent } from "@/components/ui/time-picker"

export function TimePicker() {
  const [time, setTime] = useState<string | undefined>()

  return (
    <Card>
      <CardHeader>
        <CardTitle>Time Picker</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-2">
        <TimePickerComponent value={time} onValueChange={setTime} />
      </CardContent>
    </Card>
  )
}
