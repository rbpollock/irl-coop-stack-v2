import type { Metadata } from "next"

import { BasicToggleGroup } from "./_components/basic-toggle-group"
import { ToggleGroupDisabled } from "./_components/toggle-group-disabled"
import { ToggleGroupLarge } from "./_components/toggle-group-large"
import { ToggleGroupOutline } from "./_components/toggle-group-outline"
import { ToggleGroupSingle } from "./_components/toggle-group-single"
import { ToggleGroupSmall } from "./_components/toggle-group-small"

// Define metadata for the page
// More info: https://nextjs.org/docs/app/building-your-application/optimizing/metadata
export const metadata: Metadata = {
  title: "Toggle Group",
}

export default function ToggleGroupPage() {
  return (
    <section className="container grid gap-4 p-4 md:grid-cols-2">
      <BasicToggleGroup />
      <ToggleGroupOutline />
      <ToggleGroupSingle />
      <ToggleGroupSmall />
      <ToggleGroupLarge />
      <ToggleGroupDisabled />
    </section>
  )
}
