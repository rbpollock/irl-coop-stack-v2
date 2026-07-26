"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Editor } from "@/components/ui/editor"

export function BasicEditor() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Basic Editor</CardTitle>
      </CardHeader>
      <CardContent className="flex items-center justify-center">
        <Editor className="h-32" />
      </CardContent>
    </Card>
  )
}
