"use client"

import type { Table } from "@tanstack/react-table"

import { Input } from "@/components/ui/input"
import { InvoiceTableViewOptions } from "./data-table-view-options"

interface InvoiceTableToolbarProps<TTable> {
  table: Table<TTable>
}

export function InvoiceTableToolbar<TTable>({
  table,
}: InvoiceTableToolbarProps<TTable>) {
  return (
    <div className="flex gap-x-1.5">
      <InvoiceTableViewOptions table={table} />
      <Input
        placeholder="Search by Invoice ID..."
        className="border border-input bg-background hover:bg-accent hover:text-accent-foreground"
        value={(table.getColumn("id")?.getFilterValue() as string) ?? ""}
        onChange={(event) =>
          table.getColumn("id")?.setFilterValue(event.target.value)
        }
      />
    </div>
  )
}
