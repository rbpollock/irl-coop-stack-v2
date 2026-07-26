import { z } from "zod"

export const AccountRecoveryOptionsSchema = z.object({
  option: z.enum(["email", "sms", "codes"], {
    required_error: "You need to select an account recovery option.",
  }),
})
