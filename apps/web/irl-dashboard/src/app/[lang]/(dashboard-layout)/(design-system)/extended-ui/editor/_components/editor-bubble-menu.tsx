"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Editor } from "@/components/ui/editor"

export function EditorBubbleMenu() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Editor Bubble Menu</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col justify-center gap-y-1.5">
        <Editor bubbleMenu className="h-32" />
      </CardContent>
    </Card>
  )
}
