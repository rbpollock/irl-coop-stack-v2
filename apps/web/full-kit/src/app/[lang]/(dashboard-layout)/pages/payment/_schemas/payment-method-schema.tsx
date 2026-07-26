import { z } from "zod"

const SavedCardSchema = z.object({
  savedCardId: z.string(),
})

const NewCardSchema = z.object({
  savedCardId: z.undefined(),
  cardNumber: z
    .string()
    .min(13, "Card number must be at least 13 digits")
    .max(19, "Card number must be at most 19 digits")
    .regex(/^\d+$/, "Routing number must only contain digits."),
  cardName: z.string().min(2, "Cardholder's name is required"),
  expiry: z
    .string()
    .regex(
      /^(0[1-9]|1[0-2])\/(\d{2}|\d{4})$/,
      "Expiry date must be in MM/YY or MM/YYYY format"
    ),
  cvc: z
    .string()
    .min(3, "CVC must be at least 3 digits")
    .max(4, "CVC must be at most 4 digits"),
  saveCard: z.boolean(),
})

export const PaymentMethodSchema = z.union([SavedCardSchema, NewCardSchema])
