"use client"

import { Droppable } from "@hello-pangea/dnd"

import type { DroppableProvided } from "@hello-pangea/dnd"
import type { ColumnType } from "../types"

import { CardContent } from "@/components/ui/card"
import { KanbanAddNewTaskButton } from "./kanban-add-new-task-button"
import { KanbanTaskItem } from "./kanban-task-item"

interface KanbanTaskListProps {
  column: ColumnType
}

export function KanbanTaskList({ column }: KanbanTaskListProps) {
  return (
    <Droppable droppableId={column.id}>
      {(provided: DroppableProvided) => (
        <CardContent
          ref={provided.innerRef}
          className="grid p-0 min-h-44"
          {...provided.droppableProps}
        >
          {column.tasks.map((task, index) => (
            <KanbanTaskItem key={task.id} task={task} index={index} />
          ))}
          {provided.placeholder}
          <KanbanAddNewTaskButton column={column} />
        </CardContent>
      )}
    </Droppable>
  )
}
