import type { Metadata } from "next"

import { BasicInputGroup } from "./_components/basic-input-group"
import { InputGroupCheckboxAndRadio } from "./_components/input-group-checkbox-and-radio"
import { InputGroupDropdownAndButton } from "./_components/input-group-dropdown-button"
import { InputGroupMerged } from "./_components/input-group-merged"

// Define metadata for the page
// More info: https://nextjs.org/docs/app/building-your-application/optimizing/metadata
export const metadata: Metadata = {
  title: "Input Group",
}

export default function InputGroupPage() {
  return (
    <section className="container grid gap-4 p-4 md:grid-cols-2">
      <BasicInputGroup />
      <InputGroupMerged />
      <InputGroupCheckboxAndRadio />
      <InputGroupDropdownAndButton />
    </section>
  )
}
