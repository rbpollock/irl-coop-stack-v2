"use client"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"

export function InputWithButton() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Input with Button</CardTitle>
      </CardHeader>
      <CardContent className="flex justify-center items-center">
        <div className="flex w-full max-w-sm items-center gap-x-2">
          <Input type="email" placeholder="Email" />
          <Button type="submit">Subscribe</Button>
        </div>
      </CardContent>
    </Card>
  )
}
