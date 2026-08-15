"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"

export function TextareaWithText() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Textarea with Text</CardTitle>
      </CardHeader>
      <CardContent className="flex justify-center items-center">
        <div className="grid w-full gap-1.5">
          <Label htmlFor="message-2">Your Message</Label>
          <Textarea placeholder="Type your message here." id="message-2" />
          <p className="text-sm text-muted-foreground">
            Your message will be copied to the support team.
          </p>
        </div>
      </CardContent>
    </Card>
  )
}
