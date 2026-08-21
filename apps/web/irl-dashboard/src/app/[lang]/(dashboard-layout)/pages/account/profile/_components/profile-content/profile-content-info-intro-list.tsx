import type { Profile } from "../../_lib/profile"

import { ProfileContentIntroItem } from "./profile-content-info-intro-item"

function shortId(sub: string) {
  return sub.length > 18 ? `${sub.slice(0, 8)}…${sub.slice(-6)}` : sub
}

function formatDate(iso: string | null) {
  if (!iso) return "—"
  return new Date(iso).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  })
}

export function ProfileContentIntroList({ profile }: { profile: Profile }) {
  return (
    <ul className="grid gap-y-3">
      <ProfileContentIntroItem
        title="Email"
        value={profile.email ?? "—"}
        iconName="Mail"
      />
      <ProfileContentIntroItem
        title="Account ID"
        value={shortId(profile.sub)}
        iconName="Fingerprint"
      />
      <ProfileContentIntroItem
        title="Member since"
        value={formatDate(profile.createdAt)}
        iconName="CalendarDays"
      />
      <ProfileContentIntroItem
        title="Email verified"
        value={profile.emailVerified ? "Verified" : "Not verified"}
        iconName="BadgeCheck"
      />
    </ul>
  )
}
