import { z } from "zod"

export const KanbanColumnSchema = z.object({
  title: z
    .string()
    .trim()
    .min(2, { message: "Title must contain at least 2 characters." })
    .max(50, { message: "Title must contain at most 50 characters." }),
})
