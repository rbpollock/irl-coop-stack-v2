"use client"

import { useState } from "react"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { DatePicker } from "@/components/ui/date-picker"

export function HumanFriendlyDatePicker() {
  const [date, setDate] = useState<Date | undefined>()

  return (
    <Card>
      <CardHeader>
        <CardTitle>Human Friendly Date Picker</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-2">
        <DatePicker formatStr="PPP" value={date} onValueChange={setDate} />
      </CardContent>
    </Card>
  )
}
