import type {
  ColumnType,
  KanbanActionType,
  KanbanStateType,
  TaskType,
} from "../types"

export const KanbanReducer = (
  state: KanbanStateType,
  action: KanbanActionType
): KanbanStateType => {
  switch (action.type) {
    case "addColumn": {
      const newColumn: ColumnType = {
        ...action.column,
        id: crypto.randomUUID(), // Generate a unique ID for the new column
        order: state.columns.length, // Assign the new column's order
        tasks: [], // Initialize with an empty task array
      }
      return { ...state, columns: [...state.columns, newColumn] } // Add the new column to the list
    }

    case "updateColumn": {
      return {
        ...state,
        columns: state.columns.map(
          (column) =>
            column.id === action.column.id ? { ...action.column } : column // Update the matching column
        ),
      }
    }

    case "deleteColumn": {
      return {
        ...state,
        columns: state.columns.filter(
          (column) => column.id !== action.columnId // Remove the column with the specified ID
        ),
      }
    }

    case "addTask": {
      return {
        ...state,
        columns: state.columns.map((column) => {
          if (column.id === action.columnId) {
            const newTask = {
              ...action.task,
              id: crypto.randomUUID(), // Generate a unique ID for the task
              columnId: action.columnId, // Associate task with the column
              order: column.tasks.length, // Assign order within the column
            }
            return {
              ...column,
              tasks: [...column.tasks, newTask], // Add the new task to the column's task list
            }
          }
          return column
        }),
      }
    }

    case "updateTask": {
      return {
        ...state,
        columns: state.columns.map((column) => {
          const updatedTasks = column.tasks.map((task) =>
            task.id === action.task.id
              ? { ...action.task, column_id: column.id } // Update the matching task
              : task
          )
          return { ...column, tasks: updatedTasks } // Replace the column's task list with updated tasks
        }),
      }
    }

    case "deleteTask": {
      return {
        ...state,
        columns: state.columns.map((column) => {
          const updatedTasks = column.tasks.filter(
            (task) => task.id !== action.taskId // Remove the task with the specified ID
          )
          return { ...column, tasks: updatedTasks } // Update column tasks
        }),
      }
    }

    case "reorderColumns": {
      const { sourceIndex, destinationIndex } = action
      const reorderedColumns = [...state.columns]
      const [movedColumn] = reorderedColumns.splice(sourceIndex, 1) // Remove the column from its original position
      reorderedColumns.splice(destinationIndex, 0, movedColumn) // Insert it at the new position

      return {
        ...state,
        columns: reorderedColumns.map((column, index) => ({
          ...column,
          order: index, // Reassign order based on new positions
        })),
      }
    }

    case "reorderTasks": {
      const { source, destination } = action

      // If the task is moved within the same column
      if (source.columnId === destination.columnId) {
        return {
          ...state,
          columns: state.columns.map((column) => {
            if (column.id === source.columnId) {
              const updatedTasks = [...column.tasks]
              const [movedTask] = updatedTasks.splice(source.index, 1) // Remove the task
              updatedTasks.splice(destination.index, 0, movedTask) // Insert it at the new index

              return {
                ...column,
                tasks: updatedTasks.map((task, index) => ({
                  ...task,
                  order: index, // Update task order
                })),
              }
            }
            return column
          }),
        }
      } else {
        // If the task is moved to a different column
        let movedTask: TaskType | undefined

        // Update source column to remove the task
        const updatedState = {
          ...state,
          columns: state.columns.map((column) => {
            if (column.id === source.columnId) {
              const updatedSourceTasks = [...column.tasks]
              ;[movedTask] = updatedSourceTasks.splice(source.index, 1) // Remove the task
              return { ...column, tasks: updatedSourceTasks }
            }
            return column
          }),
        }

        // Update destination column to add the task
        return {
          ...updatedState,
          columns: updatedState.columns.map((column) => {
            if (column.id === destination.columnId && movedTask) {
              const updatedDestinationTasks = [...column.tasks]
              const movedTaskWithUpdatedColumnId = {
                ...movedTask,
                column_id: destination.columnId, // Update column ID for the moved task
                order: updatedDestinationTasks.length, // Assign new order
              }
              updatedDestinationTasks.splice(
                destination.index,
                0,
                movedTaskWithUpdatedColumnId
              )

              return {
                ...column,
                tasks: updatedDestinationTasks.map((task, index) => ({
                  ...task,
                  order: index, // Update task order
                })),
              }
            }
            return column
          }),
        }
      }
    }

    case "selectColumn": {
      return { ...state, selectedColumn: action.column } // Update the selected column
    }

    case "selectTask": {
      return { ...state, selectedTask: action.task } // Update the selected task
    }

    default:
      return state // Return the current state for unknown actions
  }
}
