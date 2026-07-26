import { ProfileContentConnection } from "./profile-content-info-connection"
import { ProfileContentIntro } from "./profile-content-info-intro"

export function ProfileContentInfo() {
  return (
    <div className="flex-1 space-y-4 md:flex-none md:w-2/5">
      <ProfileContentIntro />
      <ProfileContentConnection />
    </div>
  )
}
