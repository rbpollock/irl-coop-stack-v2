import type { Metadata } from "next"

import { BasicCommand } from "./_components/basic-command"
import { CommandDialogComponent } from "./_components/command-dialog"

// Define metadata for the page
// More info: https://nextjs.org/docs/app/building-your-application/optimizing/metadata
export const metadata: Metadata = {
  title: "Command",
}

export default function CommandPage() {
  return (
    <section className="container grid gap-4 p-4 md:grid-cols-2">
      <BasicCommand />
      <CommandDialogComponent />
    </section>
  )
}
