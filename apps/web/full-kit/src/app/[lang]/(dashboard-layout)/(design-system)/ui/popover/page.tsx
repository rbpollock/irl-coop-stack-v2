import type { Metadata } from "next"

import { BasicPopover } from "./_components/basic-popover"

// Define metadata for the page
// More info: https://nextjs.org/docs/app/building-your-application/optimizing/metadata
export const metadata: Metadata = {
  title: "Popover",
}

export default function PopoverPage() {
  return (
    <section className="container grid gap-4 p-4">
      <BasicPopover />
    </section>
  )
}
