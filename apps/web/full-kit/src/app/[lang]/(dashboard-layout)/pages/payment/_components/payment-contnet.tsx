import type { PaymentType } from "../types"

import { PaymentMethodForm } from "./payment-method-form"
import { PaymentSummary } from "./payment-summary"

export function PaymentContent({ data }: { data: PaymentType }) {
  return (
    <div className="flex flex-col gap-4 lg:flex-row">
      <PaymentMethodForm data={data.savedCards} />
      <PaymentSummary data={data.summary} />
    </div>
  )
}
