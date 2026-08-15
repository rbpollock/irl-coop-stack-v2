import type { Metadata } from "next"

import { NotificationPreferences } from "./_components/notification-preferences"

// Define metadata for the page
// More info: https://nextjs.org/docs/app/building-your-application/optimizing/metadata
export const metadata: Metadata = {
  title: "Notification Settings",
}

export default function NotificationsPage() {
  return (
    <div className="grid gap-4">
      <NotificationPreferences />
    </div>
  )
}
