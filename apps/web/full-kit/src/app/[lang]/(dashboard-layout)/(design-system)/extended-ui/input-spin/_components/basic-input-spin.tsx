"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { InputSpin } from "@/components/ui/input-spin"

export function BasicInputSpin() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Basic Input Spin</CardTitle>
      </CardHeader>
      <CardContent className="flex justify-center items-center">
        <InputSpin />
      </CardContent>
    </Card>
  )
}
