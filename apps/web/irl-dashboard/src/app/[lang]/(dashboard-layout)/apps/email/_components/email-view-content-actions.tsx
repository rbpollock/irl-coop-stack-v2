"use client"

import { Archive, Clock, MoreVertical, Star, Tag, Trash2 } from "lucide-react"

import type { IconType } from "@/types"
import type { ComponentProps } from "react"

import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"

interface ActionButtonProps extends ComponentProps<typeof Button> {
  icon: IconType
  label: string
}

export function ActionButton({
  icon: Icon,
  label,
  ...props
}: ActionButtonProps) {
  return (
    <Button variant="ghost" size="icon" aria-label={label} {...props}>
      <Icon className="h-4 w-4" />
    </Button>
  )
}

export function EmailViewContentActions() {
  return (
    <div className="flex items-center justify-between">
      <div className="flex gap-2">
        <ActionButton icon={Trash2} label="Delete email" />
        <ActionButton icon={Archive} label="Archive email" />
        <ActionButton icon={Clock} label="Snooze email" />
        <ActionButton icon={Tag} label="Label email" />
      </div>
      <div className="flex items-center gap-2">
        <ActionButton icon={Star} label="Star email" />
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <ActionButton icon={MoreVertical} label="More actions" />
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem>Mark as unread</DropdownMenuItem>
            <DropdownMenuItem>Star thread</DropdownMenuItem>
            <DropdownMenuItem>Add label</DropdownMenuItem>
            <DropdownMenuItem>Mute thread</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </div>
  )
}
