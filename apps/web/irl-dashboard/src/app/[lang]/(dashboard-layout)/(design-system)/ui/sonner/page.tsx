import type { Metadata } from "next"

import { BasicSonner } from "./_components/basic-sonner"

// Define metadata for the page
// More info: https://nextjs.org/docs/app/building-your-application/optimizing/metadata
export const metadata: Metadata = {
  title: "Sonner",
}

export default function SonnerPage() {
  return (
    <section className="container grid gap-4 p-4">
      <BasicSonner />
    </section>
  )
}
