"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { InputGroup, InputGroupText } from "@/components/ui/input-group"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"

export function InputGroupCheckboxAndRadio() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Basic Input Checkbox and Radio</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-2">
        <InputGroup>
          <InputGroupText>
            <Checkbox id="terms" />
          </InputGroupText>
          <Input type="text" />
        </InputGroup>
        <InputGroup>
          <InputGroupText>
            <RadioGroup>
              <RadioGroupItem value="option1" id="option1" />
            </RadioGroup>
          </InputGroupText>
          <Input type="text" />
        </InputGroup>
        <InputGroup>
          <Input type="text" />
          <InputGroupText>
            <Checkbox id="terms" />
          </InputGroupText>
        </InputGroup>
        <InputGroup>
          <Input type="text" />
          <InputGroupText>
            <RadioGroup>
              <RadioGroupItem value="option1" id="option1" />
            </RadioGroup>
          </InputGroupText>
        </InputGroup>
      </CardContent>
    </Card>
  )
}
