import type { Metadata } from "next"

import { BasicProgress } from "./_components/basic-progress"

// Define metadata for the page
// More info: https://nextjs.org/docs/app/building-your-application/optimizing/metadata
export const metadata: Metadata = {
  title: "Progress",
}

export default function ProgressPage() {
  return (
    <section className="container grid gap-4 p-4">
      <BasicProgress />
    </section>
  )
}
