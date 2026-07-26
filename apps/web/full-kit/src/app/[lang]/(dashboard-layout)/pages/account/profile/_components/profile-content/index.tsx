import { ProfileContentInfo } from "./profile-content-info"
import { ProfileContentMainFeed } from "./profile-content-main-feed"

export function ProfileContent() {
  return (
    <section className="flex flex-col gap-4 p-4 md:flex-row">
      <ProfileContentInfo />
      <ProfileContentMainFeed />
    </section>
  )
}
