"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Textarea } from "@/components/ui/textarea"

export function BasicTextarea() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Basic Textarea</CardTitle>
      </CardHeader>
      <CardContent className="flex justify-center items-center">
        <Textarea placeholder="Type your message here." />
      </CardContent>
    </Card>
  )
}
