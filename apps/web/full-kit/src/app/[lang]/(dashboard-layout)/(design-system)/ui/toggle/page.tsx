import type { Metadata } from "next"

import { BasicToggle } from "./_components/basic-toggle"
import { ToggleDisabled } from "./_components/toggle-disabled"
import { ToggleLarge } from "./_components/toggle-large"
import { ToggleOutline } from "./_components/toggle-outline"
import { ToggleSmall } from "./_components/toggle-small"
import { ToggleWithText } from "./_components/toggle-with-text"

// Define metadata for the page
// More info: https://nextjs.org/docs/app/building-your-application/optimizing/metadata
export const metadata: Metadata = {
  title: "Toggle",
}

export default function TogglePage() {
  return (
    <section className="container grid gap-4 p-4 md:grid-cols-2">
      <BasicToggle />
      <ToggleOutline />
      <ToggleWithText />
      <ToggleSmall />
      <ToggleLarge />
      <ToggleDisabled />
    </section>
  )
}
