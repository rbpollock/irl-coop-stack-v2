import type { Metadata } from "next"

import { BasicSwitch } from "./_components/basic-switch"
import { SwitchDisabled } from "./_components/switch-disabled"

// Define metadata for the page
// More info: https://nextjs.org/docs/app/building-your-application/optimizing/metadata
export const metadata: Metadata = {
  title: "Switch",
}

export default function SwitchPage() {
  return (
    <section className="container grid gap-4 p-4 md:grid-cols-2">
      <BasicSwitch />
      <SwitchDisabled />
    </section>
  )
}
