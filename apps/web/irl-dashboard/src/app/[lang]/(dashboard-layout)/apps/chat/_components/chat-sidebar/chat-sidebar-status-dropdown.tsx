"use client"

import { CircleDashed } from "lucide-react"

import {
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
} from "@/components/ui/dropdown-menu"

const options = [
  { value: "ONLINE", label: "Online" },
  { value: "IDLE", label: "Idle" },
  { value: "DO_NOT_DISTURB", label: "Do Not Disturb" },
  { value: "INVISIBLE", label: "Invisible" },
]

type ChatSidebarStatusDropdownProps = {
  status: string
  setStatus: (val: string) => void
}

export function ChatSidebarStatusDropdown({
  status,
  setStatus,
}: ChatSidebarStatusDropdownProps) {
  return (
    <DropdownMenuSub>
      <DropdownMenuSubTrigger>
        <CircleDashed className="mr-2 h-4 w-4" />
        <span>Status</span>
      </DropdownMenuSubTrigger>
      <DropdownMenuSubContent>
        <DropdownMenuRadioGroup value={status} onValueChange={setStatus}>
          {options.map((option) => (
            <DropdownMenuRadioItem key={option.value} value={option.value}>
              {option.label}
            </DropdownMenuRadioItem>
          ))}
        </DropdownMenuRadioGroup>
      </DropdownMenuSubContent>
    </DropdownMenuSub>
  )
}
