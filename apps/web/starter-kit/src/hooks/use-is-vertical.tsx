"use client"

import { useSettings } from "@/hooks/use-settings"

export function useIsVertical() {
  const { settings } = useSettings()

  const isVertical = settings.layout === "vertical"
  return isVertical
}
