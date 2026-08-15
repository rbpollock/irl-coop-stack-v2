import Image from "next/image"

import type { VisitorsByCountryDataType } from "../types"

import { Progress } from "@/components/ui/progress"
import { PercentageChangeBadge } from "@/components/dashboards/percentage-change-badge"

export function VisitorsByCountryItem({
  data,
  totalVisitors,
}: {
  data: VisitorsByCountryDataType["countries"][number]
  totalVisitors: number
}) {
  const flagUrl = `https://purecatamphetamine.github.io/country-flag-icons/3x2/${data.countryCode}.svg`

  return (
    <li className="flex items-end justify-between gap-2">
      <div className="shrink-0 relative aspect-square h-12 w-12 bg-muted rounded-md">
        <Image src={flagUrl} alt="" fill className="rounded-md object-cover" />
      </div>
      <div className="flex-1">
        <div className="flex items-end justify-between">
          <div>
            <p className="text-lg font-semibold leading-tight">
              {data.visitors.toLocaleString()}
            </p>
            <h3 className="text-sm text-muted-foreground">
              {data.countryName}
            </h3>
          </div>
          <PercentageChangeBadge
            variant="ghost"
            value={data.percentageChange}
            className="p-0"
          />
        </div>
        <Progress value={data.visitors} max={totalVisitors} />
      </div>
    </li>
  )
}
