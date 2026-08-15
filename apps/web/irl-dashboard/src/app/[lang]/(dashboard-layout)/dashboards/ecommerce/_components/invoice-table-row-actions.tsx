"use client"

import { EllipsisVertical } from "lucide-react"

import type { Row } from "@tanstack/react-table"
import type { InvoiceType } from "../types"

import { deliveryStatusesData } from "../_data/invoices"

import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"

interface InvoiceTableRowActionsProps<TData> {
  row: Row<TData>
}

export function InvoiceTableRowActions<TData>({
  row,
}: InvoiceTableRowActionsProps<TData>) {
  const invoice = row.original as InvoiceType

  return (
    <div className="flex justify-end me-4">
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="ghost"
            size="icon"
            className="h-5 w-5 p-0.5"
            aria-label="Open actions"
          >
            <EllipsisVertical className="size-max" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-[160px]">
          <DropdownMenuItem>Edit</DropdownMenuItem>
          <DropdownMenuItem>Make a copy</DropdownMenuItem>
          <DropdownMenuItem>Mark as Paid</DropdownMenuItem>
          <DropdownMenuItem>Download Invoice</DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuSub>
            <DropdownMenuSubTrigger>
              Change Delivery Status
            </DropdownMenuSubTrigger>
            <DropdownMenuSubContent>
              <DropdownMenuRadioGroup value={invoice.deliveryStatus}>
                {deliveryStatusesData.map((status) => (
                  <DropdownMenuRadioItem
                    key={status.value}
                    value={status.value}
                  >
                    {status.label}
                  </DropdownMenuRadioItem>
                ))}
              </DropdownMenuRadioGroup>
            </DropdownMenuSubContent>
          </DropdownMenuSub>
          <DropdownMenuSeparator />
          <DropdownMenuItem className="text-destructive focus:text-destructive">
            Delete
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  )
}
