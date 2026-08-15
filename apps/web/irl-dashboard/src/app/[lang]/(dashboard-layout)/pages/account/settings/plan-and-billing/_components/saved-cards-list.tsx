"use client"

import type { z } from "zod"
import type { cardSchema } from "../_schemas/card-schema"

import { SavedCardsItem } from "./saved-cards-item"

type CardType = z.infer<typeof cardSchema>

export function SavedCardsList({ savedCards }: { savedCards: CardType[] }) {
  return (
    <ul className="space-y-2">
      {savedCards.map((card) => (
        <SavedCardsItem key={card.last4} card={card} />
      ))}
    </ul>
  )
}
