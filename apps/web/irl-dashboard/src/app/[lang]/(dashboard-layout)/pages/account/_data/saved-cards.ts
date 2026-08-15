import type { z } from "zod"
import type { cardSchema } from "../settings/plan-and-billing/_schemas/card-schema"

type CardType = z.infer<typeof cardSchema>

export const savedCardsData: CardType[] = [
  { id: 1, last4: "4242", type: "visa", default: true },
  { id: 2, last4: "5678", type: "mastercard", default: false },
]
