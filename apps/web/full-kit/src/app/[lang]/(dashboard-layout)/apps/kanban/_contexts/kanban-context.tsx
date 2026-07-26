"use client"

import { createContext, useReducer, useState } from "react"

import type { ReactNode } from "react"
import type {
  ColumnType,
  ColumnWithoutIdAndOrderAndTasksType,
  KanbanContextType,
  TaskType,
  TaskWithoutIdAndOrderAndColumnIdType,
} from "../types"

import { teamMembersData } from "../_data/team-members"

import { KanbanReducer } from "../_reducers/kanban-reducer"

// Create Kanban context
export const KanbanContext = createContext<KanbanContextType | undefined>(
  undefined
)

interface KanbanProviderProps {
  kanbanData: ColumnType[]
  children: ReactNode
}

export function KanbanProvider({ kanbanData, children }: KanbanProviderProps) {
  // Reducer to manage Kanban state
  const [kanbanState, dispatch] = useReducer(KanbanReducer, {
    columns: kanbanData,
    teamMembers: teamMembersData,
    selectedColumn: undefined,
    selectedTask: undefined,
  })

  // Sidebar state management
  const [kanbanAddTaskSidebarIsOpen, setKanbanAddTaskSidebarIsOpen] =
    useState(false)
  const [kanbanUpdateTaskSidebarIsOpen, setKanbanUpdateTaskSidebarIsOpen] =
    useState(false)
  const [kanbanAddColumnSidebarIsOpen, setKanbanAddColumnSidebarIsOpen] =
    useState(false)
  const [kanbanUpdateColumnSidebarIsOpen, setKanbanUpdateColumnSidebarIsOpen] =
    useState(false)

  // Handlers for column actions
  const handleAddColumn = (column: ColumnWithoutIdAndOrderAndTasksType) => {
    dispatch({ type: "addColumn", column })
  }

  const handleUpdateColumn = (column: ColumnType) => {
    dispatch({ type: "updateColumn", column })
  }

  const handleDeleteColumn = (columnId: ColumnType["id"]) => {
    dispatch({ type: "deleteColumn", columnId })
  }

  // Handlers for task actions
  const handleAddTask = (
    task: TaskWithoutIdAndOrderAndColumnIdType,
    columnId: ColumnType["id"]
  ) => {
    dispatch({ type: "addTask", task, columnId })
  }

  const handleUpdateTask = (task: TaskType) => {
    dispatch({ type: "updateTask", task })
  }

  const handleDeleteTask = (taskId: TaskType["id"]) => {
    dispatch({ type: "deleteTask", taskId })
  }

  // Reorder handlers
  const handleReorderColumns = (
    sourceIndex: number,
    destinationIndex: number
  ) => {
    if (sourceIndex === destinationIndex) return

    dispatch({
      type: "reorderColumns",
      sourceIndex,
      destinationIndex,
    })
  }

  const handleReorderTasks = (
    sourceColumnId: string,
    sourceIndex: number,
    destinationColumnId: string,
    destinationIndex: number
  ) => {
    if (
      sourceColumnId === destinationColumnId &&
      sourceIndex === destinationIndex
    )
      return

    dispatch({
      type: "reorderTasks",
      source: { columnId: sourceColumnId, index: sourceIndex },
      destination: { columnId: destinationColumnId, index: destinationIndex },
    })
  }

  // Selection handlers
  const handleSelectColumn = (column: ColumnType | undefined) => {
    dispatch({ type: "selectColumn", column })
  }

  const handleSelectTask = (task: TaskType | undefined) => {
    dispatch({ type: "selectTask", task })
  }

  return (
    <KanbanContext.Provider
      value={{
        kanbanState,
        kanbanAddTaskSidebarIsOpen,
        setKanbanAddTaskSidebarIsOpen,
        kanbanUpdateTaskSidebarIsOpen,
        setKanbanUpdateTaskSidebarIsOpen,
        kanbanAddColumnSidebarIsOpen,
        setKanbanAddColumnSidebarIsOpen,
        kanbanUpdateColumnSidebarIsOpen,
        setKanbanUpdateColumnSidebarIsOpen,
        handleAddColumn,
        handleUpdateColumn,
        handleDeleteColumn,
        handleAddTask,
        handleUpdateTask,
        handleDeleteTask,
        handleReorderColumns,
        handleReorderTasks,
        handleSelectColumn,
        handleSelectTask,
      }}
    >
      {children}
    </KanbanContext.Provider>
  )
}
