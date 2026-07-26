import { ChangePlan } from "./change-plan"
import { CurrentPlan } from "./current-plan"
import { PaymentMethod } from "./payment-method"
import { SavedCards } from "./saved-cards"

export function PlanAndBilling() {
  return (
    <div className="grid gap-4">
      <CurrentPlan />
      <ChangePlan />
      <PaymentMethod />
      <SavedCards />
    </div>
  )
}
