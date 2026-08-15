"use client"

import type { PaymentType } from "../types"

import { cn } from "@/lib/utils"

import { buttonVariants } from "@/components/ui/button"
import { FormControl, FormItem, FormLabel } from "@/components/ui/form"
import { RadioGroupItem } from "@/components/ui/radio-group"
import { CreditCardBrandIcon } from "@/components/credit-card-brand-icon"

export function SavedCard({
  card,
  onSelect,
}: {
  card: PaymentType["savedCards"][number]
  onSelect: (id: string) => void
}) {
  return (
    <FormItem>
      <FormLabel
        className={cn(
          buttonVariants({ variant: "outline" }),
          "h-10 w-full justify-start gap-x-2 cursor-pointer"
        )}
      >
        <FormControl>
          <RadioGroupItem value={card.id} onClick={() => onSelect(card.id)} />
        </FormControl>
        <CreditCardBrandIcon brandName={card.cardType} className="h-5 w-5" />
        <div>
          <span className="capitalize">{card.cardType}</span>{" "}
          <span>ending in {card.last4}</span>
        </div>
      </FormLabel>
    </FormItem>
  )
}
