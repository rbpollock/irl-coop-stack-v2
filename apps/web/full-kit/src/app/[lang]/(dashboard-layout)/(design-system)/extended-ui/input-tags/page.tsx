import type { Metadata } from "next"

import { BasicInputTags } from "./_components/basic-input-tags"
import { InputTagsPlaceholder } from "./_components/input-tags-placeholder"
import { InputTagsWithSuggestionsComponent } from "./_components/input-tags-with-suggestions"

// Define metadata for the page
// More info: https://nextjs.org/docs/app/building-your-application/optimizing/metadata
export const metadata: Metadata = {
  title: "Input Tags",
}

export default function InputTagsPage() {
  return (
    <section className="container grid gap-4 p-4 md:grid-cols-2">
      <BasicInputTags />
      <InputTagsPlaceholder />
      <InputTagsWithSuggestionsComponent />
    </section>
  )
}
