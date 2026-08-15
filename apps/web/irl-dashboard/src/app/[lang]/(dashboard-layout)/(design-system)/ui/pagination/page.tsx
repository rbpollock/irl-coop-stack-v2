import type { Metadata } from "next"

import { BasicPagination } from "./_components/basic-pagination"

// Define metadata for the page
// More info: https://nextjs.org/docs/app/building-your-application/optimizing/metadata
export const metadata: Metadata = {
  title: "Pagination",
}

export default function PaginationPage() {
  return (
    <section className="container grid gap-4 p-4">
      <BasicPagination />
    </section>
  )
}
