import type { Metadata } from "next"

import { BasicRadioGroup } from "./_components/basic-radio-group"
import { RadioGroupDisabled } from "./_components/radio-group-disabled"

// Define metadata for the page
// More info: https://nextjs.org/docs/app/building-your-application/optimizing/metadata
export const metadata: Metadata = {
  title: "Radio Group",
}

export default function RadioGroupPage() {
  return (
    <section className="container grid gap-4 p-4 md:grid-cols-2">
      <BasicRadioGroup />
      <RadioGroupDisabled />
    </section>
  )
}
