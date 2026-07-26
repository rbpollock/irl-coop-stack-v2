"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"

export function BasicProgress() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Basic Progress</CardTitle>
      </CardHeader>
      <CardContent className="flex justify-center items-center">
        <Progress value={33} />
      </CardContent>
    </Card>
  )
}
