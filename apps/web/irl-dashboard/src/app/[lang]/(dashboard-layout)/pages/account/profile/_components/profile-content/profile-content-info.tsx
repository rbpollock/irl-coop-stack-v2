import type { Profile } from "../../_lib/profile"

import { ProfileContentIntro } from "./profile-content-info-intro"
import { ProfileContentMembership } from "./profile-content-membership"

export function ProfileContentInfo({ profile }: { profile: Profile }) {
  return (
    <div className="flex-1 space-y-4 md:flex-none md:w-2/5">
      <ProfileContentIntro profile={profile} />
      <ProfileContentMembership profile={profile} />
    </div>
  )
}
