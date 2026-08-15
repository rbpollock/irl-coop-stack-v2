"use client"

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { InputSpin } from "@/components/ui/input-spin"

export function InputSpinMax() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Input Spin Max</CardTitle>
        <CardDescription>Set to maximum of 5</CardDescription>
      </CardHeader>
      <CardContent className="flex justify-center items-center">
        <InputSpin value={5} max={5} />
      </CardContent>
    </Card>
  )
}
