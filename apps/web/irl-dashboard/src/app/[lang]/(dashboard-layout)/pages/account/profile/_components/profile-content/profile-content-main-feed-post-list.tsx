import { postsData } from "@/app/[lang]/(dashboard-layout)/pages/account/_data/posts"

import { ProfileContentPostItem } from "./profile-content-main-feed-post-item"

export function ProfileContentPostList() {
  return (
    <div className="space-y-4">
      {postsData.map((post) => (
        <ProfileContentPostItem key={post.id} data={post} />
      ))}
    </div>
  )
}
