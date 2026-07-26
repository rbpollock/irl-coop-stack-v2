import type { Metadata } from "next"

import { BasicBreadcrumb } from "./_components/basic-breadcrumb"
import { CollapsedBreadcrumb } from "./_components/collapsed-breadcrumb"
import { CustomSeparatorBreadcrumb } from "./_components/custom-separator-breadcrumb"
import { DropdownBreadcrumb } from "./_components/dropdown-breadcrumb"
import { LinkComponentBreadcrumb } from "./_components/link-component-breadcrumb"
import { ResponsiveBreadcrumb } from "./_components/responsive-breadcrumb"

// Define metadata for the page
// More info: https://nextjs.org/docs/app/building-your-application/optimizing/metadata
export const metadata: Metadata = {
  title: "Breadcrumb",
}

export default function BreadcrumbPage() {
  return (
    <section className="container grid gap-4 p-4 md:grid-cols-2">
      <BasicBreadcrumb />
      <CustomSeparatorBreadcrumb />
      <DropdownBreadcrumb />
      <CollapsedBreadcrumb />
      <LinkComponentBreadcrumb />
      <ResponsiveBreadcrumb />
    </section>
  )
}
