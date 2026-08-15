import { z } from "zod"

import { formatFileSize } from "@/lib/utils"

import { MAX_FILES, MAX_FILE_SIZE } from "../constants"

export const formattedFileSize = formatFileSize(MAX_FILE_SIZE)

export const FileSchema = z.object({
  id: z.string(),
  url: z.string(),
  name: z.string(),
  size: z.number().max(MAX_FILE_SIZE, {
    message: `File size must be less than or equal to ${formattedFileSize}.`,
  }),
  type: z.string(),
})

export const FilesUploaderSchema = z.object({
  files: z
    .array(FileSchema)
    .min(1, { message: "At least one file must be attached." })
    .max(MAX_FILES, {
      message: `At most you can attach a maximum of ${MAX_FILES} file${
        MAX_FILES > 1 ? "s" : ""
      }.`,
    }),
})
