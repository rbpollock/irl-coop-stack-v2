"use client"

import { useState } from "react"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { InputTags } from "@/components/ui/input-tags"

export function BasicInputTags() {
  const [tags, setTags] = useState<string[]>(["React", "TypeScript"])

  return (
    <Card>
      <CardHeader>
        <CardTitle>Basic Input Tags</CardTitle>
      </CardHeader>
      <CardContent className="flex justify-center items-center">
        <InputTags tags={tags} onTagsChange={setTags} />
      </CardContent>
    </Card>
  )
}
