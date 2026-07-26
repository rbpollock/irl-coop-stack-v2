import type { Metadata } from "next"

import { BasicRating } from "./_components/basic-rating"
import { RatingIcon } from "./_components/rating-icon"
import { RatingLength } from "./_components/rating-length"
import { RatingReadOnly } from "./_components/rating-read-only"
import { RatingSizes } from "./_components/rating-sizes"
import { RatingVariants } from "./_components/rating-variants"

// Define metadata for the page
// More info: https://nextjs.org/docs/app/building-your-application/optimizing/metadata
export const metadata: Metadata = {
  title: "Rating",
}

export default function RatingPage() {
  return (
    <section className="container grid gap-4 p-4 md:grid-cols-2">
      <BasicRating />
      <RatingLength />
      <RatingSizes />
      <RatingVariants />
      <RatingReadOnly />
      <RatingIcon />
    </section>
  )
}
