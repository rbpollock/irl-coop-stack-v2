import { TrustedByCarousel } from "./trusted-by-carousel"

export function TrustedBy() {
  return (
    <section id="trusted-by" className="container grid gap-8 -mt-12">
      <h2 className="sr-only">Trusted by</h2>
      <TrustedByCarousel />
    </section>
  )
}
