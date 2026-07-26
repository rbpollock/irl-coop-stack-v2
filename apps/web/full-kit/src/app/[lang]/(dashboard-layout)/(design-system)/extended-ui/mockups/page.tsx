import type { Metadata } from "next"

import { Iphone15ProMockup } from "./_components/iphone-15-pro-mockup"
import { SafariMockup } from "./_components/safari-mockup"

// Define metadata for the page
// More info: https://nextjs.org/docs/app/building-your-application/optimizing/metadata
export const metadata: Metadata = {
  title: "Mockups",
}

export default function MockupsPage() {
  return (
    <section className="container grid gap-4 p-4">
      <Iphone15ProMockup />
      <SafariMockup />
    </section>
  )
}
