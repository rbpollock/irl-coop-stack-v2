"use client"

import type { DynamicIconNameType } from "@/types"
import type { ColumnDef } from "@tanstack/react-table"
import type { EngagementByDeviceType } from "../types"

import { formatDuration, formatPercent } from "@/lib/utils"

import { DataTableColumnHeader } from "@/components/ui/data-table/data-table-column-header"
import { Progress } from "@/components/ui/progress"
import { DynamicIcon } from "@/components/dynamic-icon"

function RenderPercentageValue({ value }: { value: number }) {
  const formattedpercentage = formatPercent(value)

  return (
    <div className="max-w-32 flex items-center gap-x-2">
      <Progress value={value * 100} />
      <span>{formattedpercentage}</span>
    </div>
  )
}

function RenderValueWithIcon({
  value,
  iconName,
}: {
  value: number | string
  iconName: DynamicIconNameType
}) {
  return (
    <div className="flex items-center gap-x-2">
      <DynamicIcon name={iconName} className="h-3 w-3" />
      <span>{value}</span>
    </div>
  )
}

export const engagementByDeviceTableColumns: ColumnDef<EngagementByDeviceType>[] =
  [
    {
      id: "deviceType",
      accessorKey: "deviceType",
      header: ({ column }) => (
        <DataTableColumnHeader
          column={column}
          title="Device Type"
          className="ms-4"
        />
      ),
      cell: ({ row }) => {
        const deviceType = row.getValue("deviceType") as string

        return <span className="ms-4 text-primary">{deviceType}</span>
      },
    },
    {
      id: "sessionDuration",
      accessorKey: "sessionDuration",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title="Session Duration" />
      ),
      cell: ({ row }) => {
        const sessionDuration = row.getValue("sessionDuration") as number

        return (
          <RenderValueWithIcon
            value={formatDuration(sessionDuration)}
            iconName="Clock"
          />
        )
      },
    },
    {
      id: "pagesPerSession",
      accessorKey: "pagesPerSession",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title="Pages per Session" />
      ),
      cell: ({ row }) => {
        const pagesPerSession = row.getValue("pagesPerSession") as number

        return <RenderValueWithIcon value={pagesPerSession} iconName="Files" />
      },
    },
    {
      id: "bounceRate",
      accessorKey: "bounceRate",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title="Bounce Rate (%)" />
      ),
      cell: ({ row }) => {
        const bounceRate = row.getValue("bounceRate") as number

        return <RenderPercentageValue value={bounceRate} />
      },
    },
    {
      id: "userPercentage",
      accessorKey: "userPercentage",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title="User Percentage (%)" />
      ),
      cell: ({ row }) => {
        const userPercentage = row.getValue("userPercentage") as number

        return <RenderPercentageValue value={userPercentage} />
      },
    },
    {
      id: "conversionRate",
      accessorKey: "conversionRate",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title="Conversion Rate (%)" />
      ),
      cell: ({ row }) => {
        const conversionRate = row.getValue("conversionRate") as number

        return <RenderPercentageValue value={conversionRate} />
      },
    },
  ]
