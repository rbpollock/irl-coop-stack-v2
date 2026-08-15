import type { SalesRepresentativeType } from "../types"

import { formatCurrency, getInitials } from "@/lib/utils"

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"

export function TopSalesRepresentativesOthersItem({
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
                className="border-2 border-muted"
              />
              <AvatarFallback className="border-2 border-muted">
                {getInitials(representative.name)}
              </AvatarFallback>
            </Avatar>
            <div className="absolute -top-2 -right-2 w-5 h-5 bg-muted rounded-full flex items-center justify-center text-xs text-foreground font-semibold">
              {index + 4}
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
