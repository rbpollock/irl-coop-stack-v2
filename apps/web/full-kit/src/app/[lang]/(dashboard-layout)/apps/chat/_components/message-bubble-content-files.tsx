import { Download } from "lucide-react"

import type { MessageType } from "../types"

import { cn, formatFileSize } from "@/lib/utils"

import { Button } from "@/components/ui/button"
import { FileThumbnail } from "@/components/ui/file-thumbnail"

export function MessageBubbleContentFiles({
  files,
  isByCurrentUser,
}: {
  files: MessageType["files"]
  isByCurrentUser: boolean
}) {
  if (!files || !files.length) return null // Return null if the files are empty

  return files.map((file) => (
    <div
      key={file.id}
      className={cn(
        "flex justify-between items-center bg-muted-foreground/20 p-4 rounded-lg break-all",
        isByCurrentUser && "bg-muted-foreground/40"
      )}
      aria-label="File"
    >
      <FileThumbnail fileName={file.name} />
      <div className="flex-1 grid mx-2 truncate">
        <span className="truncate">{file.name}</span>
        <span className="text-xs text-muted-foreground font-semibold truncate">
          {formatFileSize(file.size)}
        </span>
      </div>
      <Button variant="ghost" size="icon" aria-label="Dowmload">
        <Download className="size-4" />
      </Button>
    </div>
  ))
}
