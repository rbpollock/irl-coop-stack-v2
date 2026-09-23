import type { Profile } from "../../_lib/profile"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { ProfileContentIntroItem } from "./profile-content-info-intro-item"

function shortAddress(a: string | null | undefined) {
  if (!a) return "Not deployed"
  return a.length > 18 ? `${a.slice(0, 10)}…${a.slice(-6)}` : a
}

function formatDate(iso: string | null) {
  if (!iso) return "—"
  return new Date(iso).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  })
}

// The member's sovereign-account facts: personal Safe, onboarding state, and
// record timestamps. Reuses the intro list-item for consistent styling.
export function ProfileContentMembership({ profile }: { profile: Profile }) {
  return (
    <Card asChild>
      <article>
        <CardHeader>
          <CardTitle>Membership</CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="grid gap-y-3">
            <ProfileContentIntroItem
              title="Personal Safe"
              value={
                <span className="font-mono text-xs">
                  {shortAddress(profile.membership.personalGroup?.safe_address)}
                </span>
              }
              iconName="Wallet"
            />
            <ProfileContentIntroItem
              title="Onboarded"
              value={
                profile.onboarded
                  ? formatDate(profile.onboardedAt)
                  : "Not completed"
              }
              iconName="CircleCheck"
            />
            <ProfileContentIntroItem
              title="Last updated"
              value={formatDate(profile.updatedAt)}
              iconName="History"
            />
          </ul>
        </CardContent>
      </article>
    </Card>
  )
}
