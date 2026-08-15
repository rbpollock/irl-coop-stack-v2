import type { UserType } from "../../../types"

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { DeleteAccountForm } from "./delete-account-form"

export function DangerousZone({ user }: { user: UserType }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Dangerous Zone</CardTitle>
        <CardDescription>
          Manage sensitive settings, such as account deletion or deactivation.
          Proceed with caution.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <DeleteAccountForm user={user} />
      </CardContent>
    </Card>
  )
}
