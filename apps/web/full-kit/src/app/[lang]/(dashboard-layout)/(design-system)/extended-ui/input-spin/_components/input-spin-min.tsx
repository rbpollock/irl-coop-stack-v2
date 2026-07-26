"use client"

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { InputSpin } from "@/components/ui/input-spin"

export function InputSpinMin() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Input Spin Min</CardTitle>
        <CardDescription>Set to minimum of 5</CardDescription>
      </CardHeader>
      <CardContent className="flex justify-center items-center">
        <InputSpin value={5} min={5} />
      </CardContent>
    </Card>
  )
}
