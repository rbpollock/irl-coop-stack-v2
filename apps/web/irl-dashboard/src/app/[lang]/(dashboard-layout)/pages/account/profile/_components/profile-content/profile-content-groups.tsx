import Link from "next/link"
import { useParams } from "next/navigation"

import type { Profile } from "../../_lib/profile"

import { ensureLocalizedPathname } from "@/lib/i18n"
import { cn } from "@/lib/utils"

import { buttonVariants } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { ProfileContentGroupsList } from "./profile-content-groups-list"

// The member's groups (their Safe accounts) — replaces the mock "People you
// may know" social card with the real membership list.
export function ProfileContentGroups({ profile }: { profile: Profile }) {
  const params = useParams()
  const locale = (params.lang as string) ?? "en"

  return (
    <div className="flex-1">
      <Card asChild>
        <article>
          <CardHeader className="flex-row justify-between space-y-0">
            <CardTitle>Your groups</CardTitle>
            <Link
              href={ensureLocalizedPathname("/apps/groups", locale)}
              className={cn(
                buttonVariants({ variant: "link" }),
                "size-fit p-0"
              )}
            >
              See all
            </Link>
          </CardHeader>
          <CardContent>
            <ProfileContentGroupsList profile={profile} />
          </CardContent>
        </article>
      </Card>
    </div>
  )
}
