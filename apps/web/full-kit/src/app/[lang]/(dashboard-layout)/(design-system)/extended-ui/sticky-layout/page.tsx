import type { Metadata } from "next"

import { BasicStickyLayout } from "./_components/basic-sticky-layout"

// Define metadata for the page
// More info: https://nextjs.org/docs/app/building-your-application/optimizing/metadata
export const metadata: Metadata = {
  title: "Sticky Layout",
}

export default function StickyLayoutPage() {
  return (
    <section className="container grid gap-4 p-4">
      <BasicStickyLayout />
    </section>
  )
}
