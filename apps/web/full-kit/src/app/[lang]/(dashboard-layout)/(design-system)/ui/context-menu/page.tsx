import type { Metadata } from "next"

import { BasicContextMenu } from "./_components/basic-context-menu"

// Define metadata for the page
// More info: https://nextjs.org/docs/app/building-your-application/optimizing/metadata
export const metadata: Metadata = {
  title: "Context Menu",
}

export default function ContextMenuPage() {
  return (
    <section className="container grid gap-4 p-4">
      <BasicContextMenu />
    </section>
  )
}
