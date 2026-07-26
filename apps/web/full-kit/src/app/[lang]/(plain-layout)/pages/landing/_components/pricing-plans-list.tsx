"use client"

import { useState } from "react"

import type { PricingPlansType } from "@/components/pricing-plans"

import { ratingToPercentage } from "@/lib/utils"

import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { PricingPlans } from "@/components/pricing-plans"

const DISCOUNT_RATE = 0.15

export function PricingPlansList({ data }: { data: PricingPlansType[] }) {
  const [discountRate, setDiscountRate] = useState(0)

  const hasDiscount = discountRate !== 0
  const formattedDiscount = ratingToPercentage(DISCOUNT_RATE, 1)
  const toggleDiscount = () => setDiscountRate(hasDiscount ? 0 : DISCOUNT_RATE)

  return (
    <>
      <Label
        htmlFor="annual-billing"
        className="flex items-center justify-center gap-2"
      >
        <span>Monthly</span>
        <Switch checked={hasDiscount} onCheckedChange={toggleDiscount} />
        <span>Yearly (Save {formattedDiscount})</span>
      </Label>
      <PricingPlans data={data} discountRate={discountRate} />
    </>
  )
}
