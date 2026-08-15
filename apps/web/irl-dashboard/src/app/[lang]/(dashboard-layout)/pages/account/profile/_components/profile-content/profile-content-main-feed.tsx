import { ProfileContentCreatePost } from "./profile-content-main-feed-create-post"
import { ProfileContentPostList } from "./profile-content-main-feed-post-list"

export function ProfileContentMainFeed() {
  return (
    <div className="flex-1 space-y-4">
      <ProfileContentCreatePost />
      <ProfileContentPostList />
    </div>
  )
}
