import type { Metadata } from "next"

import { BasicDialog } from "./_components/basic-dialog"

// Define metadata for the page
// More info: https://nextjs.org/docs/app/building-your-application/optimizing/metadata
export const metadata: Metadata = {
  title: "Dialog",
}

export default function DialogPage() {
  return (
    <section className="container grid gap-4 p-4">
      <BasicDialog />
    </section>
  )
}
