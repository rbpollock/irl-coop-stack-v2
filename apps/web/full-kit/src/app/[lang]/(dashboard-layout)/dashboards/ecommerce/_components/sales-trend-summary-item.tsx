interface SalesTrendSummaryItemProps {
  title: string
  value: string
  description?: string
}

export function SalesTrendSummaryItem({
  title,
  value,
  description,
}: SalesTrendSummaryItemProps) {
  return (
    <li>
      <h3 className="text-sm text-muted-foreground">{title}</h3>
      <p className="text-2xl font-semibold">{value}</p>
      {description && (
        <p className="text-xs text-muted-foreground font-semibold">
          {description}
        </p>
      )}
    </li>
  )
}
