"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"

export function InputDisabled() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Input Disabled</CardTitle>
      </CardHeader>
      <CardContent className="flex justify-center items-center">
        <Input disabled type="email" placeholder="Email" />
      </CardContent>
    </Card>
  )
}
