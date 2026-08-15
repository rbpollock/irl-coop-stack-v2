import type { Metadata } from "next"

import { BasicTimeline } from "./_components/basic-timeline"
import { TimelineAlternating } from "./_components/timeline-alternating"
import { TimelineLeftAlign } from "./_components/timeline-left-align"
import { TimelineRightAlign } from "./_components/timeline-right-align"
import { TimelineWithLabel } from "./_components/timeline-with-label"

// Define metadata for the page
// More info: https://nextjs.org/docs/app/building-your-application/optimizing/metadata
export const metadata: Metadata = {
  title: "Timeline",
}

export default function TimelinePage() {
  return (
    <section className="container grid gap-4 p-4 md:grid-cols-2">
      <BasicTimeline />
      <TimelineAlternating />
      <TimelineLeftAlign />
      <TimelineRightAlign />
      <TimelineWithLabel />
    </section>
  )
}
