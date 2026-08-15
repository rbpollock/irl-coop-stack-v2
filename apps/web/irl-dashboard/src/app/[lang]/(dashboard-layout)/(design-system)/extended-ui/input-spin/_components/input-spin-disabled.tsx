"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { InputSpin } from "@/components/ui/input-spin"

export function InputSpinDisabled() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Input Spin Disabled</CardTitle>
      </CardHeader>
      <CardContent className="flex justify-center items-center">
        <InputSpin disabled />
      </CardContent>
    </Card>
  )
}
