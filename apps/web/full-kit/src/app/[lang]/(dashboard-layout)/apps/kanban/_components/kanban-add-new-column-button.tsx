"use client"

import { Plus } from "lucide-react"

import { Button } from "@/components/ui/button"

export function KanbanAddNewColumnButton({
  setKanbanAddColumnSidebarIsOpen,
}: {
  setKanbanAddColumnSidebarIsOpen: (value: boolean) => void
}) {
  return (
    <Button
      variant="outline"
      className="w-64 md:w-72 mx-2"
      onClick={() => setKanbanAddColumnSidebarIsOpen(true)}
    >
      <Plus className="me-2 size-4 text-muted-foreground" />
      Add New Column
    </Button>
  )
}
