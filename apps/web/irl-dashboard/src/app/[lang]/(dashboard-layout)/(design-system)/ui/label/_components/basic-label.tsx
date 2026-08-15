"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Label } from "@/components/ui/label"

export function BasicLabel() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Basic Label</CardTitle>
      </CardHeader>
      <CardContent className="flex justify-center items-center">
        <div>
          <div className="flex items-center gap-x-2">
            <Checkbox id="terms" />
            <Label htmlFor="terms">Accept terms and conditions</Label>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
