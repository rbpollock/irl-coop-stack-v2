"use client"

import { GripVertical } from "lucide-react"

import type { DraggableProvided } from "@hello-pangea/dnd"
import type { TaskType } from "../types"

import { cn } from "@/lib/utils"

import { Badge } from "@/components/ui/badge"
import { buttonVariants } from "@/components/ui/button"
import { CardHeader } from "@/components/ui/card"
import { KanbanTaskItemActions } from "./kanban-task-item-actions"

interface KanbanTaskItemHeaderProps {
  task: TaskType
  provided: DraggableProvided
}

export function KanbanTaskItemHeader({
  task,
  provided,
}: KanbanTaskItemHeaderProps) {
  return (
    <CardHeader className="flex-row items-center space-y-0 gap-x-1.5 px-3 py-3.5">
      <div
        className={cn(
          buttonVariants({
            variant: "ghost",
            size: "icon",
          }),
          "text-secondary-foreground/50 cursor-grab"
        )}
        {...provided.dragHandleProps} // Draggable props for drag-and-drop functionality
        aria-label="Move task"
      >
        <GripVertical className="size-4" />
      </div>
      <Badge>{task.label}</Badge>
      <KanbanTaskItemActions task={task} />
    </CardHeader>
  )
}
