import { WhatPeopleSayCarousel } from "./what-people-say-carousel"

export function WhatPeopleSay() {
  return (
    <section id="testimonials" className="container flex flex-col gap-8">
      <div className="text-center mx-auto space-y-1.5">
        <h2 className="text-4xl font-semibold">What People Say</h2>
        <p className="max-w-prose text-sm text-muted-foreground">
          See why developers, designers, and founders love using our admin
          dashboard template to launch fast and scale with confidence.
        </p>
      </div>
      <WhatPeopleSayCarousel />
    </section>
  )
}
