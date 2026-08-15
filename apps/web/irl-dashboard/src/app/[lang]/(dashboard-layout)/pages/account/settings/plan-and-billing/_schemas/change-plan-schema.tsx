import { z } from "zod"

export const ChangePlanSchema = z.object({
  plan: z.string(),
  isAnnual: z.boolean().default(false).optional(),
})
