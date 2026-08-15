import type { Metadata } from "next"

import { ReactIcons } from "./_components/react-icons"

// Define metadata for the page
// More info: https://nextjs.org/docs/app/building-your-application/optimizing/metadata
export const metadata: Metadata = {
  title: "React Icons",
}

export default function LucidePage() {
  return (
    <section className="container grid gap-4 p-4">
      <ReactIcons />
    </section>
  )
}
