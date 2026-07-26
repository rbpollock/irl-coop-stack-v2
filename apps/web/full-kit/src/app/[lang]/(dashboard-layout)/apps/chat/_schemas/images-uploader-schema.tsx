import { z } from "zod"

import { formatFileSize } from "@/lib/utils"

import { MAX_IMAGES, MAX_IMAGE_SIZE } from "../constants"

const formattedImageSize = formatFileSize(MAX_IMAGE_SIZE)

export const ImageSchema = z.object({
  id: z.string(),
  url: z.string(),
  name: z.string(),
  size: z.number().max(MAX_IMAGE_SIZE, {
    message: `Image size must be less than or equal to ${formattedImageSize}.`,
  }),
  type: z.string(),
})

export const ImagesUploaderSchema = z.object({
  images: z
    .array(ImageSchema)
    .min(1, { message: "At least one image must be attached." })
    .max(MAX_IMAGES, {
      message: `At most you can attach a maximum of ${MAX_IMAGES} image${
        MAX_IMAGES > 1 ? "s" : ""
      }.`,
    }),
})
