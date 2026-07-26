import type { Metadata } from "next"

import { BasicCombobox } from "./_components/basic-combobox"
import { ComboboxDropdownMenu } from "./_components/combobox-dropdown-menu"
import { ComboboxPopover } from "./_components/combobox-popover"

// Define metadata for the page
// More info: https://nextjs.org/docs/app/building-your-application/optimizing/metadata
export const metadata: Metadata = {
  title: "Combobox",
}

export default function ComboboxPage() {
  return (
    <section className="container grid gap-4 p-4 md:grid-cols-2">
      <BasicCombobox />
      <ComboboxPopover />
      <ComboboxDropdownMenu />
    </section>
  )
}
