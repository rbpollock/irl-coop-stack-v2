import { z } from "zod"

import type { CategoryType } from "../types"

import { categoriesData } from "../_data/categories"

export const EventSidebarSchema = z.object({
  url: z.string().url({ message: "Invalid url" }).optional().or(z.literal("")),
  title: z
    .string()
    .trim()
    .min(2, { message: "Title must contain at least 2 characters." })
    .max(50, { message: "Title must contain at most 50 characters." }),
  allDay: z.boolean(),
  description: z
    .string()
    .trim()
    .max(250, { message: "Description must contain at most 250 characters." })
    .optional(),
  start: z.date(),
  end: z.date(),
  category: z.custom<CategoryType>(
    (value) => categoriesData.some((category) => category === value),
    { message: "Invalid label" }
  ),
})
