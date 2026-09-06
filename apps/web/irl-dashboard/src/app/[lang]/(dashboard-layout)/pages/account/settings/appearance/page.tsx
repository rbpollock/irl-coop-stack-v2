import type { Metadata } from "next"

import { AppearanceSettings } from "./_components/appearance-settings"

export const metadata: Metadata = {
  title: "Appearance Settings",
}

export default function AppearancePage() {
  return <AppearanceSettings />
}
