import type { Metadata } from "next"

import { ButtonMisc } from "./_components/button-misc"
import { ButtonSizes } from "./_components/button-sizes"
import { ButtonVariants } from "./_components/button-variants"

// Define metadata for the page
// More info: https://nextjs.org/docs/app/building-your-application/optimizing/metadata
export const metadata: Metadata = {
  title: "Button",
}

export default function ButtonPage() {
  return (
    <section className="container grid gap-4 p-4 md:grid-cols-2">
      <ButtonVariants />
      <ButtonSizes />
      <ButtonMisc />
    </section>
  )
}
