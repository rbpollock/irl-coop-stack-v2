import { FileIcon } from "lucide-react"

import { cn } from "@/lib/utils"

interface FileThumbnailProps {
  fileName: string
  className?: string
}

export function FileThumbnail({ fileName, className }: FileThumbnailProps) {
  // Extract the file extension from the file name
  const fileExtension = fileName
    .slice(fileName.lastIndexOf(".") + 1)
    .toUpperCase()

  return (
    <div className={cn("relative size-8 text-[6px] font-black", className)}>
      <FileIcon className="size-full stroke-1" aria-labelledby="file-name" />
      <div
        className="absolute inset-0 flex justify-center items-center"
        id="file-name"
        aria-hidden
      >
        <span className="select-none">{fileExtension}</span>
        <span className="sr-only">File</span>
      </div>
    </div>
  )
}
