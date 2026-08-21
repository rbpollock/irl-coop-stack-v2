import type { Profile } from "../../_lib/profile"

import { ProfileContentGroups } from "./profile-content-groups"
import { ProfileContentInfo } from "./profile-content-info"

export function ProfileContent({ profile }: { profile: Profile }) {
  return (
    <section className="flex flex-col gap-4 p-4 md:flex-row">
      <ProfileContentInfo profile={profile} />
      <ProfileContentGroups profile={profile} />
    </section>
  )
}
