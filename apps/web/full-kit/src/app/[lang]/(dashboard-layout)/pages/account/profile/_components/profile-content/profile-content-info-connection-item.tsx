import type { UserType } from "@/types"

import { formatNumberToCompact, getInitials } from "@/lib/utils"

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"

export type UserProfileType = Pick<UserType, "name" | "avatar" | "connections">

export function ProfileContentConnectionItem({
  data,
}: {
  data: UserProfileType
}) {
  return (
    <li className="flex items-center gap-x-2">
      <Avatar>
        <AvatarImage src={data.avatar} alt="" />
        <AvatarFallback>{getInitials(data.name)}</AvatarFallback>
      </Avatar>
      <div>
        <p className="font-semibold">{data.name}</p>
        <p className="text-muted-foreground text-sm">
          {formatNumberToCompact(data.connections)} connections
        </p>
      </div>
      <Button className="ms-auto">Connect</Button>
    </li>
  )
}
