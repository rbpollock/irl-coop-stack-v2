import type { Metadata } from "next"

import { DatePicker } from "./_components/date-picker"
import { DatePickerPlaceholder } from "./_components/date-picker-placeholder"
import { DateRangePicker } from "./_components/date-range-picker"
import { DateTimePicker } from "./_components/date-time-picker"
import { HumanFriendlyDatePicker } from "./_components/human-friendly-date-picker"
import { MultipleDatesPicker } from "./_components/multiple-dates-picker"
import { TimePicker } from "./_components/time-picker"

// Define metadata for the page
// More info: https://nextjs.org/docs/app/building-your-application/optimizing/metadata
export const metadata: Metadata = {
  title: "Pickers",
}

export default function PickersPage() {
  return (
    <section className="container grid gap-4 p-4 md:grid-cols-2">
      <DatePicker />
      <TimePicker />
      <DateTimePicker />
      <MultipleDatesPicker />
      <DateRangePicker />
      <HumanFriendlyDatePicker />
      <DatePickerPlaceholder />
    </section>
  )
}
