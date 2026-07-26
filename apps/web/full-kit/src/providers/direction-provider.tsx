"use client"

import { DirectionProvider as DirectionProviderPrimitive } from "@radix-ui/react-direction"

import type { DirectionType } from "@/types"
import type { ReactNode } from "react"

export function DirectionProvider({
  direction,
  children,
}: {
  direction: DirectionType
  children: ReactNode
}) {
  return (
    <DirectionProviderPrimitive dir={direction}>
      {children}
    </DirectionProviderPrimitive>
  )
}
