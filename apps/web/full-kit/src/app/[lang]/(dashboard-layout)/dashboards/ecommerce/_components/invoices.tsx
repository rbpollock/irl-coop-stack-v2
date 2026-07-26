import { invoicesData } from "../_data/invoices"

import { InvoicesTable } from "./invoices-table"

export function Invoices() {
  return (
    <article className="col-span-full">
      <InvoicesTable data={invoicesData} />
    </article>
  )
}
