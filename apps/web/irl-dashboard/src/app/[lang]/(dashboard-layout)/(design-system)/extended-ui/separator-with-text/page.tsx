import type { Metadata } from "next"

import { BasicSeparatorWithText } from "./_components/basic-separator-with-text"

// Define metadata for the page
// More info: https://nextjs.org/docs/app/building-your-application/optimizing/metadata
export const metadata: Metadata = {
  title: "Separator with Text",
}

export default function SeparatorWithTextPage() {
  return (
    <section className="container grid gap-4 p-4">
      <BasicSeparatorWithText />
    </section>
  )
}
