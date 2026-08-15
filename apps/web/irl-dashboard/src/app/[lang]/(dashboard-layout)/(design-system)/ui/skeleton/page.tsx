import type { Metadata } from "next"

import { BasicSkeleton } from "./_components/default-skeleton"

// Define metadata for the page
// More info: https://nextjs.org/docs/app/building-your-application/optimizing/metadata
export const metadata: Metadata = {
  title: "Skeleton",
}

export default function SkeletonPage() {
  return (
    <section className="container grid gap-4 p-4">
      <BasicSkeleton />
    </section>
  )
}
