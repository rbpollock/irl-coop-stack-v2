import type { Metadata } from "next"

import { BasicCollapsible } from "./_components/basic-collapsible"

// Define metadata for the page
// More info: https://nextjs.org/docs/app/building-your-application/optimizing/metadata
export const metadata: Metadata = {
  title: "Collapsible",
}

export default function CollapsiblePage() {
  return (
    <section className="container grid gap-4 p-4">
      <BasicCollapsible />
    </section>
  )
}
