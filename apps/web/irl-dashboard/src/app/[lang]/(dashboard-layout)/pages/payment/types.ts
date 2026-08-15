import type { z } from "zod"
import type { PaymentMethodSchema } from "./_schemas/payment-method-schema"

export interface CardType {
  id: string
  cardType: string
  cardNumber: string
  cardName: string
  expiry: string
  cvc: string
  last4: string
  isDefault: boolean
}

export interface PaymentType {
  summary: {
    originalPrice: number
    savings: number
    storePickup: number
    tax: number
    total: number
  }
  savedCards: CardType[]
}

export type PaymentMethodFormType = z.infer<typeof PaymentMethodSchema>
