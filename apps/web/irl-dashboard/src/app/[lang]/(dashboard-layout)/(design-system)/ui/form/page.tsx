import type { Metadata } from "next"

import { BasicForm } from "./_components/basic-form"

// Define metadata for the page
// More info: https://nextjs.org/docs/app/building-your-application/optimizing/metadata
export const metadata: Metadata = {
  title: "Form",
}

export default function FormPage() {
  return (
    <section className="container grid gap-4 p-4">
      <BasicForm />
    </section>
  )
}
