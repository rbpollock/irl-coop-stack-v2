import type { Button } from "@/components/ui/button"
import type { ComponentProps, ReactNode } from "react"

export interface PricingType {
  title: string
  description: string
  period?: string
  price?: number | null
  features: string[]
  isFeatured?: boolean
  isCurrentPlan?: boolean
  buttonOptions?: ComponentProps<typeof Button>
  buttonContent?: ReactNode
  content?: ReactNode
  href: string
  discountRate?: number | null
}
