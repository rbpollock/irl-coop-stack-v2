"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Editor } from "@/components/ui/editor"

export function EditorPlaceholder() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Editor Placeholder</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col justify-center items-center gap-y-1.5">
        <Editor placeholder="Write your message here..." className="h-32" />
      </CardContent>
    </Card>
  )
}
