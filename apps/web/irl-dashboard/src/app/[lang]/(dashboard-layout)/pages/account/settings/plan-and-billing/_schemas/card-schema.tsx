import { z } from "zod"

export const cardSchema = z.object({
  id: z.number().int().positive(),
  last4: z
    .string()
    .length(4, { message: "last4 must be exactly 4 characters" }),
  type: z.enum(["visa", "mastercard", "amex", "discover"]),
  default: z.boolean(),
})
