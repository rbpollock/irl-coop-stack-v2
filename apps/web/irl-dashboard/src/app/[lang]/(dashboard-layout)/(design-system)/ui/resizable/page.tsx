import type { Metadata } from "next"

import { BasicResizable } from "./_components/basic-resizable"
import { ResizableHandleComponent } from "./_components/resizable-handle"
import { ResizableVertical } from "./_components/resizable-vertical"

// Define metadata for the page
// More info: https://nextjs.org/docs/app/building-your-application/optimizing/metadata
export const metadata: Metadata = {
  title: "Resizable",
}

export default function ResizablePage() {
  return (
    <section className="container grid gap-4 p-4 md:grid-cols-2">
      <div className="grid gap-4">
        <BasicResizable />
        <ResizableHandleComponent />
      </div>
      <ResizableVertical />
    </section>
  )
}
