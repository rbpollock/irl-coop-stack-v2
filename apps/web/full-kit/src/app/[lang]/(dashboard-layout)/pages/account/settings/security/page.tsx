import type { Metadata } from "next"

import { userData } from "@/data/user"

import { AccountRecoveryOptions } from "./_components/account-recovery-options"
import { ChangePassword } from "./_components/change-password"
import { Passkeys } from "./_components/passkeys"
import { RecentLogs } from "./_components/recent-logs"
import { SafeWallet } from "./_components/safe-wallet"
import { SecurityPreferences } from "./_components/security-preferences"

// Define metadata for the page
// More info: https://nextjs.org/docs/app/building-your-application/optimizing/metadata
export const metadata: Metadata = {
  title: "Security Settings",
}

export default function SecurityPage() {
  return (
    <div className="grid gap-4">
      <SafeWallet />
      <Passkeys />
      <ChangePassword />
      <SecurityPreferences user={userData} />
      <AccountRecoveryOptions user={userData} />
      <RecentLogs />
    </div>
  )
}
