import type { Profile } from "../../_lib/profile"

import { ProfileContentGroupsItem } from "./profile-content-groups-item"

export function ProfileContentGroupsList({ profile }: { profile: Profile }) {
  const groups = profile.membership.groups
  if (groups.length === 0) {
    return <p className="text-sm text-muted-foreground">No groups yet.</p>
  }
  return (
    <ul className="grid gap-y-2">
      {groups.map((group) => (
        <ProfileContentGroupsItem key={group.id} group={group} />
      ))}
    </ul>
  )
}
