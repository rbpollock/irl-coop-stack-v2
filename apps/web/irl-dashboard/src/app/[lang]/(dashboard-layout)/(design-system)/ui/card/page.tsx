import type { Metadata } from "next"

import { BasicCard } from "./_components/basic-card"

// Define metadata for the page
// More info: https://nextjs.org/docs/app/building-your-application/optimizing/metadata
export const metadata: Metadata = {
  title: "Card",
}

export default function CardPage() {
  return (
    <section className="container grid gap-4 p-4">
      <BasicCard />
    </section>
  )
}
