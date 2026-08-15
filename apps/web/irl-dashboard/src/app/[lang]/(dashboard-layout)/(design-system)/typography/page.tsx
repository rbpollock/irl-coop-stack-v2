import type { Metadata } from "next"

import { FontFamilies } from "./_components/font-families"
import { TextStyles } from "./_components/text-styles"

// Define metadata for the page
// More info: https://nextjs.org/docs/app/building-your-application/optimizing/metadata
export const metadata: Metadata = {
  title: "Typography",
}

export default function TypographyPage() {
  return (
    <section className="container grid gap-4 p-4">
      <TextStyles />
      <FontFamilies />
    </section>
  )
}
