"use client"

import { Draggable } from "@hello-pangea/dnd"

import type { DraggableProvided } from "@hello-pangea/dnd"
import type { ColumnType } from "../types"

import { KanbanColumnItemHeader } from "./kanban-column-item-header"
import { KanbanTaskList } from "./kanban-task-list"

interface KanbanColumnProps {
  column: ColumnType
  index: number
}

export function KanbanColumnItem({ column, index }: KanbanColumnProps) {
  return (
    <Draggable
      draggableId={column.id} // A unique identifier for this column, which helps the library track and move the item
      index={index} // The position of this column in the root, used for reordering columns when drag-and-drop occurs
    >
      {/* A render callback function that provides the necessary props
        for the Draggable component to function properly */}
      {(provided: DraggableProvided) => (
        <div
          ref={provided.innerRef}
          className="w-64 h-fit md:w-72"
          {...provided.draggableProps} // Draggable props for drag-and-drop functionality
        >
          <KanbanColumnItemHeader column={column} provided={provided} />
          <KanbanTaskList column={column} />
        </div>
      )}
    </Draggable>
  )
}
