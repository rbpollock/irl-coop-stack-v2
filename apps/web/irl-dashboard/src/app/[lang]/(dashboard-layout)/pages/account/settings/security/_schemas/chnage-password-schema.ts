import { z } from "zod"

export const ChangePasswordSchema = z.object({
  currentPassword: z.string().min(8, {
    message: "Current password must contain at least 8 characters",
  }),
  newPassword: z.string().min(8, {
    message: "New password must contain at least 8 characters",
  }),
  confirmPassword: z.string().min(8, {
    message: "Confirm password must contain at least 8 characters",
  }),
})
