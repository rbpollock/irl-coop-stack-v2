import type { Metadata } from "next"

import { BasicKeyboard } from "./_components/basic-keyboard"

// Define metadata for the page
// More info: https://nextjs.org/docs/app/building-your-application/optimizing/metadata
export const metadata: Metadata = {
  title: "Keyboard",
}

export default function KeyboardPage() {
  return (
    <section className="container grid gap-4 p-4">
      <BasicKeyboard />
    </section>
  )
}
