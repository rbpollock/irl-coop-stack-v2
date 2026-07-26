"use client"

import { useState } from "react"

import { suggestionsData } from "../_data/suggestions"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { InputTagsWithSuggestions } from "@/components/ui/input-tags"

export function InputTagsWithSuggestionsComponent() {
  const [tags, setTags] = useState<string[]>(["React", "TypeScript"])

  return (
    <Card>
      <CardHeader>
        <CardTitle>Tags Input with Suggestions</CardTitle>
      </CardHeader>
      <CardContent className="flex justify-center items-center">
        <InputTagsWithSuggestions
          suggestions={suggestionsData}
          tags={tags}
          onTagsChange={setTags}
        />
      </CardContent>
    </Card>
  )
}
