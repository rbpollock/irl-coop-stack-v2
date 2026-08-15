import { formatCurrency } from "@/lib/utils"

interface PaymentSummaryRowProps {
  label: string
  value: number
  valueClassName?: string
}

export function PaymentSummaryRow({
  label,
  value,
  valueClassName,
}: PaymentSummaryRowProps) {
  return (
    <dl className="flex items-center justify-between gap-4">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className={valueClassName || "text-accent-foreground"}>
        {formatCurrency(value)}
      </dd>
    </dl>
  )
}
