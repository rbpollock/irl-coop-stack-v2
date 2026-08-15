import type { RevenueBySourceType } from "../types"

import { RevenueBySourceItem } from "./revenue-by-source-item"

export function RevenueBySourceList({
  data,
}: {
  data: RevenueBySourceType["sources"]
}) {
  return (
    <ul className="space-y-1">
      {data.map((item) => (
        <RevenueBySourceItem key={item.name} data={item} />
      ))}
    </ul>
  )
}
