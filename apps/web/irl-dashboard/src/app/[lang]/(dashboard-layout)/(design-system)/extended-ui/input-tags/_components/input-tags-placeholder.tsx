"use client"

import { useState } from "react"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { InputTags } from "@/components/ui/input-tags"

export function InputTagsPlaceholder() {
  const [tags, setTags] = useState<string[]>([])

  return (
    <Card>
      <CardHeader>
        <CardTitle>Input Tags Placeholder</CardTitle>
      </CardHeader>
      <CardContent className="flex justify-center items-center">
        <InputTags
          placeholder="Add tags..."
          tags={tags}
          onTagsChange={setTags}
        />
      </CardContent>
    </Card>
  )
}
