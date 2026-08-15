import type { UserType } from "../../../types"

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { SecurityPreferencesForm } from "./security-preferences-form"

export function SecurityPreferences({ user }: { user: UserType }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Security Preferences</CardTitle>
        <CardDescription>
          Update your security settings to enhance account protection and manage
          security features.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <SecurityPreferencesForm user={user} />
      </CardContent>
    </Card>
  )
}
