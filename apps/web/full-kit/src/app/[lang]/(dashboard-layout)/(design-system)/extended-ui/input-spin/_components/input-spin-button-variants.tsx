"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { InputSpin } from "@/components/ui/input-spin"

export function InputSpinButtonVariants() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Input Spin Button Variants</CardTitle>
      </CardHeader>
      <CardContent className="grid justify-center items-center gap-2">
        <div className="space-y-1.5">
          <h4>Primary</h4>
          <InputSpin />
        </div>
        <div className="space-y-1.5">
          <h4>Secondary</h4>
          <InputSpin buttonVariant="secondary" />
        </div>
        <div className="space-y-1.5">
          <h4>Outline</h4>
          <InputSpin buttonVariant="outline" />
        </div>
        <div className="space-y-1.5">
          <h4>Ghost</h4>
          <InputSpin buttonVariant="ghost" />
        </div>
        <div className="space-y-1.5">
          <h4>Destructive</h4>
          <InputSpin buttonVariant="destructive" />
        </div>
      </CardContent>
    </Card>
  )
}
