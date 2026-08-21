import Link from "next/link"
import { useParams } from "next/navigation"
import { ChevronRight } from "lucide-react"

import { ensureLocalizedPathname } from "@/lib/i18n"
import { getInitials } from "@/lib/utils"

import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Badge } from "@/components/ui/badge"

import type { ProfileGroup } from "../../_lib/profile"

const PRIVACY_LABEL: Record<string, string> = {
  open: "Open",
  members: "Members",
  hidden: "Hidden",
}

function shortAddress(a: string | null | undefined) {
  if (!a) return null
  return a.length > 18 ? `${a.slice(0, 10)}…${a.slice(-6)}` : a
}

export function ProfileContentGroupsItem({ group }: { group: ProfileGroup }) {
  const params = useParams()
  const locale = (params.lang as string) ?? "en"
  const role = group.roles[0] ?? "member"
  const safe = shortAddress(group.safe_address)

  return (
    <li>
      <Link
        href={ensureLocalizedPathname(`/apps/groups/${group.id}`, locale)}
        className="flex items-center gap-x-2 rounded-md p-1 hover:bg-accent"
      >
        <Avatar className="size-9">
          <AvatarFallback>{getInitials(group.name)}</AvatarFallback>
        </Avatar>
        <div className="min-w-0">
          <p className="truncate font-semibold">{group.name}</p>
          <p className="text-muted-foreground text-sm">
            {role}
            {safe ? ` · ${safe}` : ""}
          </p>
        </div>
        <Badge variant="secondary" className="ms-auto">
          {PRIVACY_LABEL[group.privacy] ?? group.privacy}
        </Badge>
        <ChevronRight className="h-4 w-4 text-muted-foreground" />
      </Link>
    </li>
  )
}
