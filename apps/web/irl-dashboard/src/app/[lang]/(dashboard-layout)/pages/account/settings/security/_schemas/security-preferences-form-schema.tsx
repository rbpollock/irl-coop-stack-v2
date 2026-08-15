import { z } from "zod"

export const SecurityPreferencesSchema = z.object({
  twoFactorAuth: z.boolean().default(false).optional(),
  loginAlerts: z.boolean().default(true).optional(),
})
