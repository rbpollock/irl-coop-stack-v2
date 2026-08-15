import { z } from "zod"

const BankSchema = z.object({
  paymentType: z.enum(["bank", "card"], {
    required_error: "You need to select a payment type.",
  }),
  accountNumber: z
    .string()
    .min(10, "Account number must be at least 10 digits.")
    .max(20, "Account number must be at most 20 digits.")
    .regex(/^\d+$/, "Account number must only contain digits."),
  routingNumber: z
    .string()
    .length(9, "Routing number must be exactly 9 digits.")
    .regex(/^\d+$/, "Routing number must only contain digits."),
  saveCard: z.boolean(),
})

const CardSchema = z.object({
  paymentType: z.enum(["bank", "card"], {
    required_error: "You need to select a payment type.",
  }),
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

export const PaymentMethodSchema = z.union([BankSchema, CardSchema])
