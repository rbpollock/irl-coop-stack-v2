import type { Metadata } from "next"

import { BasicDropdownMenu } from "./_components/basic-dropdown-menu"
import { DropdownMenuCheckboxes } from "./_components/dropdown-menu-checkboxes"
import { DropdownMenuRadioGroupComponent } from "./_components/dropdown-menu-radio-group"

// Define metadata for the page
// More info: https://nextjs.org/docs/app/building-your-application/optimizing/metadata
export const metadata: Metadata = {
  title: "Dropdown Menu",
}

export default function DropdownMenuPage() {
  return (
    <section className="container grid gap-4 p-4 md:grid-cols-2">
      <BasicDropdownMenu />
      <DropdownMenuCheckboxes />
      <DropdownMenuRadioGroupComponent />
    </section>
  )
}
