import type { Metadata } from "next"

import { BasicSlider } from "./_components/basic-slider"

// Define metadata for the page
// More info: https://nextjs.org/docs/app/building-your-application/optimizing/metadata
export const metadata: Metadata = {
  title: "Slider",
}

export default function SliderPage() {
  return (
    <section className="container grid gap-4 p-4">
      <BasicSlider />
    </section>
  )
}
