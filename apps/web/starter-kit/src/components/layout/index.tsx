"use client"

import type { ReactNode } from "react"

import { useIsVertical } from "@/hooks/use-is-vertical"
import { HorizontalLayout } from "./horizontal-layout"
import { VerticalLayout } from "./vertical-layout"

export function Layout({ children }: { children: ReactNode }) {
  const isVertical = useIsVertical()

  return isVertical ? (
    <VerticalLayout>{children}</VerticalLayout>
  ) : (
    <HorizontalLayout>{children}</HorizontalLayout>
  )
}
