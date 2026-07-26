"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { InputPhone } from "@/components/ui/input-phone"

export function BasicInputPhone() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Basic Input Phone</CardTitle>
      </CardHeader>
      <CardContent className="h-40 flex justify-center items-center">
        <InputPhone className="max-w-72" />
      </CardContent>
    </Card>
  )
}
