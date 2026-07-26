import { z } from "zod"

export const NotificationPreferencesSchema = z.object({
  security: z.object({
    email: z.boolean(),
    browser: z.boolean(),
    sms: z.boolean(),
  }),
  communication: z.object({
    email: z.boolean(),
    browser: z.boolean(),
    sms: z.boolean(),
  }),
  meetups: z.object({
    email: z.boolean(),
    browser: z.boolean(),
    sms: z.boolean(),
  }),
})
