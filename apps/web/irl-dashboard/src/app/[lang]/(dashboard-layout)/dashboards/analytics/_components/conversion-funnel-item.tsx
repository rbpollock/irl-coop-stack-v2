"use client"

import type { ConversionFunnelType } from "../types"

export function ConversionFunnelItem({
  data,
}: {
  data: ConversionFunnelType["funnelSteps"][number]
}) {
  return (
    <li className="flex flex-col items-center text-center">
      <p className="text-xl font-semibold sm:text-2xl">
        {data.value.toLocaleString()}
      </p>
      <h3 className="text-sm text-muted-foreground">{data.name}</h3>
    </li>
  )
}
