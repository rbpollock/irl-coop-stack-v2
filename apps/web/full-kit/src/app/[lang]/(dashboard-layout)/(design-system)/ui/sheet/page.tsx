import type { Metadata } from "next"

import { BasicSheet } from "./_components/basic-sheet"
import { SheetSide } from "./_components/sheet-side"

// Define metadata for the page
// More info: https://nextjs.org/docs/app/building-your-application/optimizing/metadata
export const metadata: Metadata = {
  title: "Sheet",
}

export default function SheetPage() {
  return (
    <section className="container grid gap-4 p-4 md:grid-cols-2">
      <BasicSheet />
      <SheetSide />
    </section>
  )
}
