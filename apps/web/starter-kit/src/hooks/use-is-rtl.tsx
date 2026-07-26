"use client"

import { useDirection } from "@radix-ui/react-direction"

export function useIsRtl() {
  const direction = useDirection()

  const isRtl = direction === "rtl"
  return isRtl
}
