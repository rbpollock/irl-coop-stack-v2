import type { ReactNode } from "react"
import type { ColumnType } from "../types"

import { KanbanProvider } from "../_contexts/kanban-context"
import { KanbanSidebar } from "./kanban-sidebar"

export function KanbanWrapper({
  kanbanData,
  children,
}: {
  kanbanData: ColumnType[]
  children: ReactNode
}) {
  return (
    <KanbanProvider kanbanData={kanbanData}>
      <div className="flex">
        <KanbanSidebar />
        {children}
      </div>
    </KanbanProvider>
  )
}
