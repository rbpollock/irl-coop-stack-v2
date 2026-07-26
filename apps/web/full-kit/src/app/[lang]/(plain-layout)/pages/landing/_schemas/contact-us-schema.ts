import { z } from "zod"

export const ContactUsSchema = z.object({
  name: z
    .string()
    .trim()
    .min(2, { message: "Name must contain at least 2 characters" })
    .max(50, { message: "Name must contain at most 50 characters" }),
  email: z
    .string()
    .toLowerCase()
    .trim()
    .email({ message: "Invalid email address" })
    .min(2, { message: "Email must contain at least 2 characters" })
    .max(50, { message: "Email must contain at most 50 characters" }),
  message: z
    .string()
    .trim()
    .min(2, { message: "Message must contain at least 2 character" })
    .max(5000, { message: "Message must contain at most 5000 characters" }),
})
