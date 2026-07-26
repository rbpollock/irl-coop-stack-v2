import type { Metadata } from "next"

import { BasicBadge } from "./_components/basic-badge"

// Define metadata for the page
// More info: https://nextjs.org/docs/app/building-your-application/optimizing/metadata
export const metadata: Metadata = {
  title: "Badge",
}

export default function BadgePage() {
  return (
    <section className="container grid gap-4 p-4">
      <BasicBadge />
    </section>
  )
}
