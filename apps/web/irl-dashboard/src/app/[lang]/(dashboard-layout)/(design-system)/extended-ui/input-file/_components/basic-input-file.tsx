"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { InputFile } from "@/components/ui/input-file"

export function BasicInputFile() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Basic Input File</CardTitle>
      </CardHeader>
      <CardContent className="flex items-center justify-center">
        <InputFile />
      </CardContent>
    </Card>
  )
}
