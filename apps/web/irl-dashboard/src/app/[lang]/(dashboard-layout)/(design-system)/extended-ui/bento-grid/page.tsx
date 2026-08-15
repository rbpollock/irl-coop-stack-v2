import type { Metadata } from "next"

import { BasicBentoGrid } from "./_components/basic-bento-grid"

// Define metadata for the page
// More info: https://nextjs.org/docs/app/building-your-application/optimizing/metadata
export const metadata: Metadata = {
  title: "Bento Grid",
}

export default function BentoGridPage() {
  return (
    <section className="container grid gap-4 p-4">
      <BasicBentoGrid />
    </section>
  )
}
