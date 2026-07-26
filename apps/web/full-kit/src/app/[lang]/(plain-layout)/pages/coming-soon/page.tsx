import { ComingSoon } from "@/components/pages/coming-soon"

export default function ComingSoonPgae() {
  // Get the current date and add two days
  const targetDate = new Date()
  targetDate.setDate(targetDate.getDate() + 2)

  return <ComingSoon targetDate={targetDate} />
}
