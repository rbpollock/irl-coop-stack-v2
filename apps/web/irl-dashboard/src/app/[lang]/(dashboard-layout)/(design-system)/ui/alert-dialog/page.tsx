import type { Metadata } from "next"

import { BasicAlertDialog } from "./_components/basic-alert-dialog"

// Define metadata for the page
// More info: https://nextjs.org/docs/app/building-your-application/optimizing/metadata
export const metadata: Metadata = {
  title: "Alert Dialog",
}

export default function AlertDialogPage() {
  return (
    <section className="container grid gap-4 p-4">
      <BasicAlertDialog />
    </section>
  )
}
