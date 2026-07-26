import type { Metadata } from "next"

import { kanbanData } from "./_data/kanban"

import { Kanban } from "./_components/kanban"
import { KanbanWrapper } from "./_components/kanban-wrapper"

// Define metadata for the page
// More info: https://nextjs.org/docs/app/building-your-application/optimizing/metadata
export const metadata: Metadata = {
  title: "Kanban",
}

export default function KanbanPage() {
  return (
    <KanbanWrapper kanbanData={kanbanData}>
      <Kanban />
    </KanbanWrapper>
  )
}
