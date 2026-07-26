import type { Metadata } from "next"

import { BasicAlert } from "./_components/basic-alert"

// Define metadata for the page
// More info: https://nextjs.org/docs/app/building-your-application/optimizing/metadata
export const metadata: Metadata = {
  title: "Alert",
}

export default function AlertPage() {
  return (
    <section className="container grid gap-4 p-4">
      <BasicAlert />
    </section>
  )
}
