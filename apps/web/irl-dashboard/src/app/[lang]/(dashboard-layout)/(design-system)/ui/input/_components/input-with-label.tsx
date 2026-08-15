"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

export function InputWithLabel() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Input with Label</CardTitle>
      </CardHeader>
      <CardContent className="flex justify-center items-center">
        <div className="grid w-full max-w-sm items-center gap-1.5">
          <Label htmlFor="email">Email</Label>
          <Input type="email" id="email" placeholder="Email" />
        </div>
      </CardContent>
    </Card>
  )
}
