import type { Metadata } from "next"

import { userData } from "@/data/user"

import { DangerousZone } from "./_components/general/dangerous-zone"
import { ProfileInfo } from "./_components/general/profile-info"

// Define metadata for the page
// More info: https://nextjs.org/docs/app/building-your-application/optimizing/metadata
export const metadata: Metadata = {
  title: "Profile Information Settings",
}

export default function ProfileInfoPage() {
  return (
    <div className="grid gap-4">
      <ProfileInfo user={userData} />
      <DangerousZone user={userData} />
    </div>
  )
}
