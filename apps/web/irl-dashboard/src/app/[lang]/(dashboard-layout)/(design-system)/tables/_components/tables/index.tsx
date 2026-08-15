import BasicTable from "./basic-table"
import ContextualClasses from "./contextual-classes"
import { DataTable } from "./data-table"
import TableWithCaption from "./table-with-caption"
import TableWithFooter from "./table-with-footer"

export function Tables() {
  return (
    <section className="container grid gap-4 p-4">
      <BasicTable />
      <TableWithFooter />
      <TableWithCaption />
      <ContextualClasses />
      <DataTable />
    </section>
  )
}
