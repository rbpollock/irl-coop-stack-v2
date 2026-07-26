import type { Metadata } from "next"

import { Tables } from "./_components/tables"

// Define metadata for the page
// More info: https://nextjs.org/docs/app/building-your-application/optimizing/metadata
export const metadata: Metadata = {
  title: "Tables",
}

export default function TablesPage() {
  return <Tables />
}
