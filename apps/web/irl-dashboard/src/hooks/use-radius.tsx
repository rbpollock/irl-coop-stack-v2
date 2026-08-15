"use client"

import { remToPx } from "@/lib/utils"

import { useSettings } from "@/hooks/use-settings"

export function useRadius(asPx = true) {
  const { settings } = useSettings()

  let radius = Number(settings.radius)
  if (asPx) {
    radius = remToPx(radius)
  }

  return radius
}
