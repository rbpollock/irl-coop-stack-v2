import { z } from "zod"

export const FormLayoutsSchema = z.object({
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
  phoneNumber: z
    .string()
    .min(10, { message: "Phone Number must contain at least 10 digits." })
    .max(15, { message: "Username must contain at most 15 digits." }),
  state: z
    .string()
    .trim()
    .min(2, { message: "State must contain at least 2 characters." })
    .max(50, { message: "State must contain at most 50 characters." }),
  country: z
    .string()
    .trim()
    .min(2, { message: "Country must contain at least 2 characters." })
    .max(56, { message: "Country must contain at most 56 characters." }),
  address: z
    .string()
    .trim()
    .min(2, { message: "Address must contain at least 2 characters." })
    .max(100, { message: "Address must contain at most 100 characters." }),
})
