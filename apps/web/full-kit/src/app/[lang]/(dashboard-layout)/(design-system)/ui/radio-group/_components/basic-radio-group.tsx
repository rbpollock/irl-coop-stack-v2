"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"

export function BasicRadioGroup() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Basic Radio Group</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-2">
        <RadioGroup defaultValue="option-one">
          <div className="flex justify-center items-center gap-x-2">
            <RadioGroupItem value="option-one" id="option-one" />
            <Label htmlFor="option-one">Option One</Label>
          </div>
          <div className="flex justify-center items-center gap-x-2">
            <RadioGroupItem value="option-two" id="option-two" />
            <Label htmlFor="option-two">Option Two</Label>
          </div>
        </RadioGroup>
      </CardContent>
    </Card>
  )
}
