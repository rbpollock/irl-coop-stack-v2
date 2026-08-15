import { z } from "zod"

export const EmailComposerSchema = z.object({
  to: z
    .string()
    .email({ message: "Invalid email address" })
    .toLowerCase()
    .trim(),
  cc: z
    .string()
    .email({ message: "Invalid email address" })
    .toLowerCase()
    .trim()
    .optional(),
  bcc: z
    .string()
    .email({ message: "Invalid email address" })
    .toLowerCase()
    .trim()
    .optional(),
  subject: z
    .string()
    .trim()
    .min(1, { message: "Subject must contain at least 1 character" })
    .max(100, { message: "Subject must contain at most 100 characters" }),
  content: z
    .string()
    .trim()
    .min(1, { message: "Content must contain at least 1 character" })
    .max(5000, { message: "Content must contain at most 5000 characters" }),
})
