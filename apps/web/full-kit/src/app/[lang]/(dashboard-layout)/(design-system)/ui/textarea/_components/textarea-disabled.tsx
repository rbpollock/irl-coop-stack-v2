"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Textarea } from "@/components/ui/textarea"

export function TextareaDisabled() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Textarea Disabled</CardTitle>
      </CardHeader>
      <CardContent className="flex justify-center items-center">
        <Textarea placeholder="Type your message here." disabled />
      </CardContent>
    </Card>
  )
}
