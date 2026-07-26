import type { DynamicIconNameType } from "@/types"
import type { ReactNode } from "react"

import { DynamicIcon } from "@/components/dynamic-icon"

export function ProfileContentIntroItem({
  iconName,
  title,
  value,
}: {
  iconName: DynamicIconNameType
  title: string
  value: string | ReactNode
}) {
  return (
    <li className="inline-flex items-baseline gap-x-1">
      <DynamicIcon name={iconName} className="h-4 w-4 translate-y-[0.2rem]" />
      <p>
        {title} <span className="text-primary">{value}</span>
      </p>
    </li>
  )
}
