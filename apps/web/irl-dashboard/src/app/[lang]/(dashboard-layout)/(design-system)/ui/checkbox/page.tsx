import type { Metadata } from "next"

import { BasicCheckbox } from "./_components/basic-checkbox"
import { CheckboxDisabled } from "./_components/checkbox-disabled"

// Define metadata for the page
// More info: https://nextjs.org/docs/app/building-your-application/optimizing/metadata
export const metadata: Metadata = {
  title: "Checkbox",
}

export default function CheckboxPage() {
  return (
    <section className="container grid gap-4 p-4 md:grid-cols-2">
      <BasicCheckbox />
      <CheckboxDisabled />
    </section>
  )
}
