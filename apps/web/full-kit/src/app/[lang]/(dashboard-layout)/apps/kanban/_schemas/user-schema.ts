import { z } from "zod"

export const UserSchema = z.object({
  id: z.string(),
  username: z.string().trim().toLowerCase(),
  name: z.string().trim(),
  avatar: z.string().optional(),
})
