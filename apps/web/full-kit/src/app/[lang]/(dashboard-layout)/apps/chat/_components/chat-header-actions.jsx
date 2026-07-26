import { EllipsisVertical, Phone, Video } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"

export function ChatHeaderActions() {
  return (
    <div className="flex gap-1 ms-auto">
      <Button variant="ghost" size="icon">
        <Phone className="size-4" />
      </Button>
      <Button variant="ghost" size="icon">
        <Video className="size-4" />
      </Button>

      {/* More Actions Dropdown */}
      <DropdownMenu>
        <DropdownMenuTrigger className="self-center" asChild>
          <Button variant="ghost" size="icon" aria-label="More actions">
            <EllipsisVertical className="size-4" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem>Search</DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem className="text-destructive focus:text-destructive">
            Report
          </DropdownMenuItem>
          <DropdownMenuItem className="text-destructive focus:text-destructive">
            Mute
          </DropdownMenuItem>
          <DropdownMenuItem className="text-destructive focus:text-destructive">
            Block
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  )
}
