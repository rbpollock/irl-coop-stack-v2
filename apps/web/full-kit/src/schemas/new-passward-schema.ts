import { z } from "zod"

export const NewPasswordSchema = z
  .object({
    password: z.string().min(8, {
      message: "Password must contain at least 8 characters",
    }),
    confirmPassword: z.string().min(8, {
      message: "Confirm password must contain at least 8 characters",
    }),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: "Passwords must match",
    path: ["confirmPassword"],
  })
