import type { Metadata } from "next"

import { ChangePlan } from "./_components/change-plan"
import { CurrentPlan } from "./_components/current-plan"
import { PaymentMethod } from "./_components/payment-method"
import { SavedCards } from "./_components/saved-cards"

// Define metadata for the page
// More info: https://nextjs.org/docs/app/building-your-application/optimizing/metadata
export const metadata: Metadata = {
  title: "Plan and Billing Settings",
}

export default function PlanAndBillingPage() {
  return (
    <div className="grid gap-4">
      <CurrentPlan />
      <ChangePlan />
      <PaymentMethod />
      <SavedCards />
    </div>
  )
}
