"use client"

import { useState } from "react"
import { EllipsisVertical } from "lucide-react"

import type { ColumnType } from "../types"

import { useKanbanContext } from "../_hooks/use-kanban-context"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuShortcut,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"

interface KanbanColumnActionsProps {
  column: ColumnType
}

export function KanbanColumnActions({ column }: KanbanColumnActionsProps) {
  const [open, onOpenChange] = useState(false)
  const {
    setKanbanUpdateColumnSidebarIsOpen,
    handleSelectColumn,
    handleDeleteColumn,
  } = useKanbanContext()

  return (
    <DropdownMenu open={open} onOpenChange={onOpenChange}>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          className="flex h-8 w-8 p-0 ms-auto data-[state=open]:bg-muted"
          aria-label="More actions"
        >
          <EllipsisVertical className="h-4 w-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-[160px]">
        <DropdownMenuItem
          onClick={() => {
            handleSelectColumn(column)
            onOpenChange(false)
            setKanbanUpdateColumnSidebarIsOpen(true)
          }}
        >
          Edit
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem
          className="text-destructive focus:text-destructive"
          onClick={() => handleDeleteColumn(column.id)}
        >
          Delete
          <DropdownMenuShortcut>⌘⌫</DropdownMenuShortcut>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
