import type { Metadata } from "next"

import { BasicHoverCard } from "./_components/basic-hover-card"

// Define metadata for the page
// More info: https://nextjs.org/docs/app/building-your-application/optimizing/metadata
export const metadata: Metadata = {
  title: "Hover Card",
}

export default function HoverCardPage() {
  return (
    <section className="container grid gap-4 p-4">
      <BasicHoverCard />
    </section>
  )
}
