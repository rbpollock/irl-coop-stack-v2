import type { Metadata } from "next"

import { BasicTooltip } from "./_components/basic-tooltip"

// Define metadata for the page
// More info: https://nextjs.org/docs/app/building-your-application/optimizing/metadata
export const metadata: Metadata = {
  title: "Tooltip",
}

export default function TooltipPage() {
  return (
    <section className="container grid gap-4 p-4">
      <BasicTooltip />
    </section>
  )
}
