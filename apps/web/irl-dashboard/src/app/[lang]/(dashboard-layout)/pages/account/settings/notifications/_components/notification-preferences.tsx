import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { NotificationPreferencesForm } from "./notifications-preferenes-form"

export function NotificationPreferences() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Notification Preferences</CardTitle>
        <CardDescription>
          Adjust your settings to control which notifications you receive.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <NotificationPreferencesForm />
      </CardContent>
    </Card>
  )
}
