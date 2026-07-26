import type { InvoiceType } from "../types"

export const invoicesData: InvoiceType[] = [
  { id: "INV001", status: "Paid", method: "Credit Card", amount: "$250.00" },
  { id: "INV002", status: "Pending", method: "PayPal", amount: "$150.00" },
  {
    id: "INV003",
    status: "Overdue",
    method: "Bank Transfer",
    amount: "$300.00",
  },
]
