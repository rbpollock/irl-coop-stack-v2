"use client"

import { Droppable } from "@hello-pangea/dnd"

import type { DroppableProvided } from "@hello-pangea/dnd"

import { useKanbanContext } from "../_hooks/use-kanban-context"
import { ScrollArea } from "@/components/ui/scroll-area"
import { KanbanAddNewColumnButton } from "./kanban-add-new-column-button"
import { KanbanColumnItem } from "./kanban-column-item"

export function KanbanColumnList() {
  const { kanbanState, setKanbanAddColumnSidebarIsOpen } = useKanbanContext()

  return (
    <ScrollArea orientation="horizontal" className="container flex-1 w-0 p-0">
      <Droppable
        droppableId="root" // Unique identifier for the droppable area. Used to track drag-and-drop events
        type="Column" // Specifies the type of draggable items this droppable area will accept. Helps differentiate between column and task movements
        direction="horizontal" // Indicates the drag direction within the droppable area (horizontal layout for Kanban columns)
      >
        {/* A render callback function that provides the necessary props for the Droppable component to function properly */}
        {(provided: DroppableProvided) => (
          <div
            ref={provided.innerRef}
            {...provided.droppableProps} // Droppable props for drag-and-drop functionality
            className="flex gap-x-4 p-4"
          >
            {kanbanState.columns.map((column, index) => (
              <KanbanColumnItem key={column.id} column={column} index={index} />
            ))}
            {/* Placeholder for maintaining layout integrity by creating a visual space for the dragged item */}
            {provided.placeholder}
            <KanbanAddNewColumnButton
              setKanbanAddColumnSidebarIsOpen={setKanbanAddColumnSidebarIsOpen}
            />
          </div>
        )}
      </Droppable>
    </ScrollArea>
  )
}
