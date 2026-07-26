import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { ProfileContentIntroList } from "./profile-content-info-intro-list"

export function ProfileContentIntro() {
  return (
    <Card asChild>
      <article>
        <CardHeader>
          <CardTitle>Intro</CardTitle>
        </CardHeader>
        <CardContent>
          <ProfileContentIntroList />
        </CardContent>
      </article>
    </Card>
  )
}
