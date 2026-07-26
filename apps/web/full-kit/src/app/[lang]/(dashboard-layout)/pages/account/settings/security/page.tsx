import type { Metadata } from "next"

import { userData } from "@/data/user"

import { AccountRecoveryOptions } from "./_components/account-recovery-options"
import { ChangePassword } from "./_components/change-password"
import { RecentLogs } from "./_components/recent-logs"
import { SecurityPreferences } from "./_components/security-preferences"

// Define metadata for the page
// More info: https://nextjs.org/docs/app/building-your-application/optimizing/metadata
export const metadata: Metadata = {
  title: "Security Settings",
}

export default function SecurityPage() {
  return (
    <div className="grid gap-4">
      <ChangePassword />
      <SecurityPreferences user={userData} />
      <AccountRecoveryOptions user={userData} />
      <RecentLogs />
    </div>
  )
}
