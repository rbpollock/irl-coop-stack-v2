import type { Metadata } from "next"

import { BasicLabel } from "./_components/basic-label"

// Define metadata for the page
// More info: https://nextjs.org/docs/app/building-your-application/optimizing/metadata
export const metadata: Metadata = {
  title: "Label",
}

export default function LabelPage() {
  return (
    <section className="container grid gap-4 p-4">
      <BasicLabel />
    </section>
  )
}
