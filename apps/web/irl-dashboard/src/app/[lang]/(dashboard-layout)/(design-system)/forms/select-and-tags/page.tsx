import type { Metadata } from "next"

import { BasicInputTags } from "../../extended-ui/input-tags/_components/basic-input-tags"
import { InputTagsPlaceholder } from "../../extended-ui/input-tags/_components/input-tags-placeholder"
import { InputTagsWithSuggestionsComponent } from "../../extended-ui/input-tags/_components/input-tags-with-suggestions"
import { BasicSelect } from "../../ui/select/_components/basic-select"
import { SelectScrollable } from "../../ui/select/_components/select-scrollable"

// Define metadata for the page
// More info: https://nextjs.org/docs/app/building-your-application/optimizing/metadata
export const metadata: Metadata = {
  title: "Select and Tags",
}

export default function SelectAndTagsPage() {
  return (
    <section className="container grid gap-4 p-4 md:grid-cols-2">
      <BasicSelect />
      <SelectScrollable />
      <BasicInputTags />
      <InputTagsPlaceholder />
      <InputTagsWithSuggestionsComponent />
    </section>
  )
}
