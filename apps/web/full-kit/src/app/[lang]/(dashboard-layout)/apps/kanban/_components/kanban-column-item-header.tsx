"use client"

import { GripVertical } from "lucide-react"

import type { DraggableProvided } from "@hello-pangea/dnd"
import type { ColumnType } from "../types"

import { cn } from "@/lib/utils"

import { buttonVariants } from "@/components/ui/button"
import { CardHeader, CardTitle } from "@/components/ui/card"
import { KanbanColumnActions } from "./kanban-column-actions"

interface KanbanColumnItemHeaderProps {
  column: ColumnType
  provided: DraggableProvided
}

export function KanbanColumnItemHeader({
  column,
  provided,
}: KanbanColumnItemHeaderProps) {
  return (
    <CardHeader className="flex-row items-center space-y-0 gap-x-1.5 p-0">
      <div
        className={cn(
          buttonVariants({ variant: "ghost", size: "icon" }),
          "text-secondary-foreground/50 cursor-grab"
        )}
        {...provided.dragHandleProps} // Draggable props for drag-and-drop functionality
        aria-label="Move task"
      >
        <GripVertical className="size-4" />
      </div>
      <CardTitle className="me-auto">{column.title}</CardTitle>
      <KanbanColumnActions column={column} />
    </CardHeader>
  )
}
