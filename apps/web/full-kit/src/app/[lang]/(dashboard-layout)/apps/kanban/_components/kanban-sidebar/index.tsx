import { KanbanAddColumnSidebar } from "./kanban-add-column-sidebar"
import { KanbanAddTaskSidebar } from "./kanban-add-task-sidebar"
import { KanbanUpdateColumnSidebar } from "./kanban-update-column-sidebar"
import { KanbanUpdateTaskSidebar } from "./kanban-update-task-sidebar"

export function KanbanSidebar() {
  return (
    <>
      <KanbanAddTaskSidebar />
      <KanbanUpdateTaskSidebar />
      <KanbanAddColumnSidebar />
      <KanbanUpdateColumnSidebar />
    </>
  )
}
