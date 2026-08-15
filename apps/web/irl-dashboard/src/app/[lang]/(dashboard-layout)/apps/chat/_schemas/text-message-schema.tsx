import { z } from "zod"

export const TextMessageSchema = z.object({
  text: z
    .string()
    .trim()
    .min(1, "Message text cannot be empty")
    .max(280, "Message text cannot exceed 280 characters"),
})
