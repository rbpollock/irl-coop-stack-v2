"use client"

import type { Table } from "@tanstack/react-table"

import { EngagementByDeviceTableViewOptions } from "./engagement-by-device-table-view-options"

interface EngagementByDeviceTableToolbarProps<TTable> {
  table: Table<TTable>
}

export function EngagementByDeviceTableToolbar<TTable>({
  table,
}: EngagementByDeviceTableToolbarProps<TTable>) {
  return (
    <div>
      <EngagementByDeviceTableViewOptions table={table} />
    </div>
  )
}
