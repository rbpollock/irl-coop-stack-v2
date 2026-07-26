import { z } from "zod"

export const RegisterSchema = z.object({
  firstName: z
    .string()
    .trim()
    .min(2, { message: "First Name must contain at least 2 characters." })
    .max(50, { message: "First Name must contain at most 50 characters." }),
  lastName: z
    .string()
    .trim()
    .min(2, { message: "Last Name must contain at least 2 characters." })
    .max(50, { message: "Last Name must contain at most 50 characters." }),
  username: z
    .string()
    .toLowerCase()
    .trim()
    .min(3, { message: "Username must contain at least 3 characters." })
    .max(50, { message: "Username must contain at most 50 characters." }),
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
    .regex(/(?=.*[a-zA-Z])/, {
      message: "Password must contain at least one letter.",
    })
    .regex(/(?=.*[0-9])/, {
      message: "Password must contain at least one number.",
    }),
})
