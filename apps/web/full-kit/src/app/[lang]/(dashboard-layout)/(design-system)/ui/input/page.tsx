import type { Metadata } from "next"

import { BasicInput } from "./_components/basic-input"
import { InputDisabled } from "./_components/input-disabled"
import { InputFile } from "./_components/input-file"
import { InputWithButton } from "./_components/input-with-button"
import { InputWithLabel } from "./_components/input-with-label"

// Define metadata for the page
// More info: https://nextjs.org/docs/app/building-your-application/optimizing/metadata
export const metadata: Metadata = {
  title: "Input",
}

export default function InputPage() {
  return (
    <section className="container grid gap-4 p-4 md:grid-cols-2">
      <BasicInput />
      <InputFile />
      <InputDisabled />
      <InputWithLabel />
      <InputWithButton />
    </section>
  )
}
