import type { SalesRepresentativeType } from "../types"

import { cn, formatCurrency, getInitials } from "@/lib/utils"

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"

const avatarColor = [
  "border-yellow-400 dark:border-yellow-500",
  "border-gray-300 dark:border-gray-400",
  "border-amber-600 dark:border-amber-700",
]

const badgeColor = [
  "bg-yellow-400 dark:bg-yellow-500",
  "bg-gray-300 dark:bg-gray-400",
  "bg-amber-600 dark:bg-amber-700",
]

export function TopSalesRepresentativesTop3Item({
  representative,
  index,
}: {
  representative: SalesRepresentativeType["representatives"][0]
  index: number
}) {
  return (
    <li key={representative.name}>
      <Card>
        <CardContent className="flex items-center gap-x-4 py-3 px-6">
          <div className="relative">
            <Avatar>
              <AvatarImage
                src={representative.avatar}
                alt="Avatar"
                className={cn("border-2 border-muted", avatarColor[index])}
              />
              <AvatarFallback
                className={cn("border-2 border-muted", avatarColor[index])}
              >
                {getInitials(representative.name)}
              </AvatarFallback>
            </Avatar>
            <div
              className={cn(
                "absolute -top-2 -right-2 w-5 h-5 bg-muted rounded-full flex items-center justify-center text-xs text-foreground font-semibold",
                badgeColor[index]
              )}
            >
              {index + 1}
            </div>
          </div>
          <div className="flex-1 w-0">
            <h3 className="text-sm font-semibold break-all truncate">
              {representative.name}
            </h3>
            <p className="text-xs text-muted-foreground font-semibold break-all truncate">
              {representative.email}
            </p>
          </div>
          <Badge>{formatCurrency(representative.sales)}</Badge>
        </CardContent>
      </Card>
    </li>
  )
}
