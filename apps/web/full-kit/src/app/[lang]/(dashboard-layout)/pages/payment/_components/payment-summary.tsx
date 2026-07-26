import type { PaymentType } from "../types"

import { Card } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import { PaymentSummaryRow } from "./payment-summary-row"

export function PaymentSummary({ data }: { data: PaymentType["summary"] }) {
  return (
    <Card className="h-fit w-full space-y-4 p-6 bg-accent lg:w-3/5">
      <div className="space-y-2">
        <PaymentSummaryRow label="Original price" value={data.originalPrice} />
        <PaymentSummaryRow
          label="Savings"
          value={data.savings}
          valueClassName="text-success"
        />
        <PaymentSummaryRow label="Store Pickup" value={data.storePickup} />
        <PaymentSummaryRow label="Tax" value={data.tax} />
      </div>
      <Separator />
      <PaymentSummaryRow
        label="Total"
        value={data.total}
        valueClassName="font-semibold"
      />
    </Card>
  )
}
