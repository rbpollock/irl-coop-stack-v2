import type { Metadata } from "next"

import { BasicDrawer } from "./_components/basic-drawer"
import { DrawerResponsiveDialog } from "./_components/drawer-responsive-dialog"

// Define metadata for the page
// More info: https://nextjs.org/docs/app/building-your-application/optimizing/metadata
export const metadata: Metadata = {
  title: "Drawer",
}

export default function DrawerPage() {
  return (
    <section className="container grid gap-4 p-4 md:grid-cols-2">
      <BasicDrawer />
      <DrawerResponsiveDialog />
    </section>
  )
}
