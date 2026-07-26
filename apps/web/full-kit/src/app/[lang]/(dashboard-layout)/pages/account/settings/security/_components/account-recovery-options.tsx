import type { UserType } from "../../../types"

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { AccountRecoveryOptionsForm } from "./account-recovery-options-form"

export function AccountRecoveryOptions({ user }: { user: UserType }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Account Recovery Options</CardTitle>
        <CardDescription>
          Set up and manage recovery options to easily regain access to your
          account if you forget your password.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <AccountRecoveryOptionsForm user={user} />
      </CardContent>
    </Card>
  )
}
