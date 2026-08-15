// Refer to react-beautiful-dnd README.md file for more details https://github.com/atlassian/react-beautiful-dnd
"use client"

import { DragDropContext } from "@hello-pangea/dnd"

import type { DropResult } from "@hello-pangea/dnd"

import { useKanbanContext } from "../_hooks/use-kanban-context"
import { KanbanColumnList } from "./kanban-column-list"

export function Kanban() {
  const { handleReorderColumns, handleReorderTasks } = useKanbanContext()

  const handleDragDrop = (result: DropResult) => {
    const { source, destination, type } = result

    // Ignore if there's no destination
    if (!destination) return

    if (type === "Column") {
      handleReorderColumns(source.index, destination.index)
    } else {
      handleReorderTasks(
        source.droppableId,
        source.index,
        destination.droppableId,
        destination.index
      )
    }
  }

  return (
    <DragDropContext onDragEnd={handleDragDrop}>
      <KanbanColumnList />
    </DragDropContext>
  )
}
