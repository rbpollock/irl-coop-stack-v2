"use client"

import { useContext } from "react"

import { KanbanContext } from "../_contexts/kanban-context"

export function useKanbanContext() {
  const context = useContext(KanbanContext)
  if (context === undefined) {
    throw new Error("useKanbanContext must be used within a KanbanProvider")
  }
  return context
}
