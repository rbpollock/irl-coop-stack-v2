import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

import type { Profile } from "../../_lib/profile"
import { ProfileContentIntroList } from "./profile-content-info-intro-list"

export function ProfileContentIntro({ profile }: { profile: Profile }) {
  return (
    <Card asChild>
      <article>
        <CardHeader>
          <CardTitle>Intro</CardTitle>
        </CardHeader>
        <CardContent>
          <ProfileContentIntroList profile={profile} />
        </CardContent>
      </article>
    </Card>
  )
}
