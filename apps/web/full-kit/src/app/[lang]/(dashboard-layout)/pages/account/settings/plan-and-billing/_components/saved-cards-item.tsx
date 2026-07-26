"use client"

import { EllipsisVertical } from "lucide-react"

import type { z } from "zod"
import type { cardSchema } from "../_schemas/card-schema"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { CreditCardBrandIcon } from "@/components/credit-card-brand-icon"

type CardType = z.infer<typeof cardSchema>

export function SavedCardsItem({ card }: { card: CardType }) {
  return (
    <li className="flex justify-between items-center space-y-0 px-4 py-2 border rounded-lg">
      <h4 className="flex justify-center items-center gap-2">
        <CreditCardBrandIcon brandName={card.type} />
        <span className="shrink-0">**** **** **** {card.last4}</span>
        {/* Display a `Default` badge if the card is marked as the default */}
        {card.default && <Badge>Default</Badge>}
      </h4>
      <div>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon">
              <EllipsisVertical className="size-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent>
            <DropdownMenuItem disabled={card.default}>
              Set Default
            </DropdownMenuItem>
            <DropdownMenuItem className="text-destructive focus:text-destructive">
              Delete
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </li>
  )
}
