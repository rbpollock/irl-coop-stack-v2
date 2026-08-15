import type { Metadata } from "next"

import { BasicNavigationMenu } from "./_components/basic-navigation-menu"

// Define metadata for the page
// More info: https://nextjs.org/docs/app/building-your-application/optimizing/metadata
export const metadata: Metadata = {
  title: "Navigation Menu",
}

export default function NavigationMenuPage() {
  return (
    <section className="container grid gap-4 p-4">
      <BasicNavigationMenu />
    </section>
  )
}
