import type { Metadata } from "next"

import { BasicSelect } from "./_components/basic-select"
import { SelectScrollable } from "./_components/select-scrollable"

// Define metadata for the page
// More info: https://nextjs.org/docs/app/building-your-application/optimizing/metadata
export const metadata: Metadata = {
  title: "Select",
}

export default function SelectPage() {
  return (
    <section className="container grid gap-4 p-4 md:grid-cols-2">
      <BasicSelect />
      <SelectScrollable />
    </section>
  )
}
