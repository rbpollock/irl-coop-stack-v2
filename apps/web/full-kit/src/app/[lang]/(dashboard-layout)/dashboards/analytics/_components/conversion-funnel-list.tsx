"use client"

import type { ConversionFunnelType } from "../types"

import { ConversionFunnelItem } from "./conversion-funnel-item"

export function ConversionFunnelList({
  data,
}: {
  data: ConversionFunnelType["funnelSteps"]
}) {
  return (
    <ul
      style={{
        gridTemplateColumns: `repeat(${data.length}, 1fr)`,
      }}
      className="w-full grid gap-x-3 px-6"
    >
      {data.map((stage) => (
        <ConversionFunnelItem key={stage.name} data={stage} />
      ))}
    </ul>
  )
}
