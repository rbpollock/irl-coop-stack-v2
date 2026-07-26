import type { Metadata } from "next"

import { BasicScrollArea } from "./_components/basic-scroll-area"
import { ScrollAreaHorizontal } from "./_components/scroll-area-horizontal"

// Define metadata for the page
// More info: https://nextjs.org/docs/app/building-your-application/optimizing/metadata
export const metadata: Metadata = {
  title: "ScrollArea",
}

export default function ScrollAreaPage() {
  return (
    <section className="container grid gap-4 p-4 md:grid-cols-2">
      <BasicScrollArea />
      <ScrollAreaHorizontal />
    </section>
  )
}
