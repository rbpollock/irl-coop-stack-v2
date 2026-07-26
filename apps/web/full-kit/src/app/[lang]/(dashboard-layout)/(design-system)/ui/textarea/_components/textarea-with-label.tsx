"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"

export function TextareaWithLabel() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Textarea with Label</CardTitle>
      </CardHeader>
      <CardContent className="flex justify-center items-center">
        <div className="grid w-full gap-1.5">
          <Label htmlFor="message">Your message</Label>
          <Textarea placeholder="Type your message here." id="message" />
        </div>
      </CardContent>
    </Card>
  )
}
