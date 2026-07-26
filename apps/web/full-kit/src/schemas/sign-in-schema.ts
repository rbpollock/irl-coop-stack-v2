import { z } from "zod"

export const SignInSchema = z.object({
  email: z
    .string()
    .email({ message: "Invalid email address" })
    .toLowerCase()
    .trim(),
  password: z
    .string()
    .min(8, {
      message: "Password must contain at least 8 characters",
    })
    .max(250, {
      message: "Password must contain at most 250 characters",
    })
    .regex(/(?=.*[a-zA-Z])/, {
      message: "Password must contain at least one letter.",
    })
    .regex(/(?=.*[0-9])/, {
      message: "Password must contain at least one number.",
    }),
})
