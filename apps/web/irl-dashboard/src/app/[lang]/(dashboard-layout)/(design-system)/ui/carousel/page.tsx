import type { Metadata } from "next"

import { BasicCarousel } from "./_components/basic-carousel"
import { CarouselAutoplay } from "./_components/carousel-autoplay"
import { CarouselOrientation } from "./_components/carousel-orientation"
import { CarouselSizes } from "./_components/carousel-sizes"
import { CarouselSpacing } from "./_components/carousel-spacing"

// Define metadata for the page
// More info: https://nextjs.org/docs/app/building-your-application/optimizing/metadata
export const metadata: Metadata = {
  title: "Carousel",
}

export default function CarouselPage() {
  return (
    <section className="container grid gap-4 p-4 md:grid-cols-2">
      <BasicCarousel />
      <CarouselOrientation />
      <CarouselSizes />
      <CarouselSpacing />
      <CarouselAutoplay />
    </section>
  )
}
