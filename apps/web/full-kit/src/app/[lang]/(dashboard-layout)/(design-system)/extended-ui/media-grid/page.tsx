import type { Metadata } from "next"

import { BasicMediaGrid } from "./_components/basic-media-grid"
import { MediaGridLimit } from "./_components/media-grid-limit"
import { MediaGridOneItem } from "./_components/media-grid-one-item"
import { MediaGridTwoItems } from "./_components/media-grid-two-items"

// Define metadata for the page
// More info: https://nextjs.org/docs/app/building-your-application/optimizing/metadata
export const metadata: Metadata = {
  title: "Media Grid",
}

export default function MediaGridPage() {
  return (
    <section className="container grid gap-4 p-4 md:grid-cols-2">
      <BasicMediaGrid />
      <MediaGridOneItem />
      <MediaGridTwoItems />
      <MediaGridLimit />
    </section>
  )
}
