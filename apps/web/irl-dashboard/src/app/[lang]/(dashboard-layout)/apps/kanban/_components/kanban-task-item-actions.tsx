"use client"

import { useState } from "react"
import { EllipsisVertical } from "lucide-react"

import type { TaskType } from "../types"

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

interface KanbanTaskItemActionsProps {
  task: TaskType
}

export function KanbanTaskItemActions({ task }: KanbanTaskItemActionsProps) {
  const [open, onOpenChange] = useState(false)
  const {
    setKanbanUpdateTaskSidebarIsOpen,
    handleSelectTask,
    handleDeleteTask,
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
            handleSelectTask(task)
            onOpenChange(false)
            setKanbanUpdateTaskSidebarIsOpen(true)
          }}
        >
          Edit
        </DropdownMenuItem>
        <DropdownMenuItem>Make a copy</DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem
          className="text-destructive focus:text-destructive"
          onClick={() => handleDeleteTask(task.id)}
        >
          Delete
          <DropdownMenuShortcut>⌘⌫</DropdownMenuShortcut>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
