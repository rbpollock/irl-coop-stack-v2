import type { UserType } from "../../../types"

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { ProfileInfoForm } from "./profile-info-form"

export function ProfileInfo({ user }: { user: UserType }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Profile Information</CardTitle>
        <CardDescription>Update your public profile details.</CardDescription>
      </CardHeader>
      <CardContent>
        <ProfileInfoForm user={user} />
      </CardContent>
    </Card>
  )
}
