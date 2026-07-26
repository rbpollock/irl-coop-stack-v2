import type { Metadata } from "next"

import { BasicCalendar } from "./_components/basic-calendar"

// Define metadata for the page
// More info: https://nextjs.org/docs/app/building-your-application/optimizing/metadata
export const metadata: Metadata = {
  title: "Calendar",
}

export default function CalendarPage() {
  return (
    <section className="container grid gap-4 p-4">
      <BasicCalendar />
    </section>
  )
}
