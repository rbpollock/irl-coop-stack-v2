import type { Metadata } from "next"

import { BasicColors } from "./_components/basic-colors"
import { BordersAndRings } from "./_components/borders-and-rings"
import { ChartColors } from "./_components/chart-colors"

// Define metadata for the page
// More info: https://nextjs.org/docs/app/building-your-application/optimizing/metadata
export const metadata: Metadata = {
  title: "Colors",
}

export default function ColorsPage() {
  return (
    <section className="container grid gap-4 p-4 md:grid-cols-2">
      <BasicColors />
      <div className="flex flex-col gap-4">
        <ChartColors />
        <BordersAndRings />
      </div>
    </section>
  )
}
