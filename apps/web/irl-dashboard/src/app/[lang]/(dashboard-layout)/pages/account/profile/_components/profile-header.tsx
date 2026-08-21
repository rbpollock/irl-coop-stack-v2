import Link from "next/link"
import { UserPen } from "lucide-react"

import { ensureLocalizedPathname } from "@/lib/i18n"
import { cn, getInitials } from "@/lib/utils"

import { AspectRatio } from "@/components/ui/aspect-ratio"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { buttonVariants } from "@/components/ui/button"

import type { Profile } from "../_lib/profile"

function shortAddress(a: string | null | undefined) {
  if (!a) return null
  return a.length > 18 ? `${a.slice(0, 10)}…${a.slice(-6)}` : a
}

export function ProfileHeader({
  locale,
  profile,
}: {
  locale: string
  profile: Profile
}) {
  const name = profile.name ?? profile.email ?? "Member"
  const personalSafe = shortAddress(
    profile.membership.personalGroup?.safe_address
  )
  const groupCount = profile.membership.groupCount

  return (
    <section className="bg-background border-y border-border">
      <AspectRatio ratio={5 / 1} className="bg-muted" />
      <div className="relative w-full flex flex-col items-center gap-2 p-4 md:flex-row">
        <Avatar className="size-32 -mt-20 md:size-40">
          <AvatarImage
            src={profile.avatar ?? undefined}
            alt="Profile Avatar"
            className="border-4 border-background"
          />
          <AvatarFallback className="border-4 border-background">
            {getInitials(name)}
          </AvatarFallback>
        </Avatar>
        <Link
          href={ensureLocalizedPathname("/pages/account/settings", locale)}
          className={cn(
            buttonVariants({ variant: "ghost", size: "icon" }),
            "absolute top-4 end-4"
          )}
          aria-label="Edit your profile"
        >
          <UserPen className="size-4" />
        </Link>
        <div className="text-center md:text-start">
          <div>
            <h1 className="text-2xl font-bold line-clamp-1">{name}</h1>
            {profile.email && (
              <p className="text-muted-foreground line-clamp-1">
                {profile.email}
              </p>
            )}
          </div>
          <div className="inline-flex w-full flex-wrap gap-x-1">
            <p className="text-primary after:content-['\00b7'] after:mx-1">
              {groupCount} {groupCount === 1 ? "group" : "groups"}
            </p>
            {personalSafe && (
              <p className="font-mono text-primary">{personalSafe}</p>
            )}
          </div>
        </div>
      </div>
    </section>
  )
}
