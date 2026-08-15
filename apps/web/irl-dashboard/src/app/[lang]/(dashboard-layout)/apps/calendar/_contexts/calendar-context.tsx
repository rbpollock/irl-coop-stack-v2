"use client"

import { createContext, useReducer, useState } from "react"

import type { CalendarApi } from "@fullcalendar/core/index.js"
import type { ReactNode } from "react"
import type {
  CalendarContextType,
  CategoryType,
  EventType,
  EventWithoutIdType,
} from "../types"

import { categoriesData } from "../_data/categories"

import { CalendarReducer } from "../_reducers/calendar-reducer"

// Create Kanban context
export const CalendarContext = createContext<CalendarContextType | undefined>(
  undefined
)

export function CalendarProvider({
  events,
  children,
}: {
  events: EventType[]
  children: ReactNode
}) {
  // Reducer to manage Calendar state
  const [calendarState, dispatch] = useReducer(CalendarReducer, {
    initalEvents: events,
    events,
    selectedCategories: [...categoriesData],
  })

  // State management
  const [calendarApi, setCalendarApi] = useState<null | CalendarApi>(null)
  const [eventSidebarIsOpen, setEventSidebarIsOpen] = useState(false)

  // Handlers for event actions
  const handleAddEvent = (event: EventWithoutIdType) => {
    dispatch({
      type: "addEvent",
      event: { ...event, id: calendarState.events.length.toString() },
    })
  }

  const handleUpdateEvent = (event: EventType) => {
    dispatch({ type: "updateEvent", event })
  }

  const handleDeleteEvent = (eventId: EventType["id"]) => {
    dispatch({ type: "deleteEvent", eventId })
  }

  // Selection handlers
  const handleSelectEvent = (event?: EventType) => {
    dispatch({ type: "selectEvent", event: event })
  }

  const handleSelectCategory = (category: CategoryType) => {
    dispatch({ type: "selectCategory", category })
  }

  const handleSelectAllCategories = (isSelectAllCategories: boolean) => {
    dispatch({ type: "selectAllCategories", isSelectAllCategories })
  }

  return (
    <CalendarContext.Provider
      value={{
        calendarState,
        calendarApi,
        setCalendarApi,
        eventSidebarIsOpen,
        setEventSidebarIsOpen,
        handleUpdateEvent,
        handleAddEvent,
        handleDeleteEvent,
        handleSelectEvent,
        handleSelectCategory,
        handleSelectAllCategories,
      }}
    >
      {children}
    </CalendarContext.Provider>
  )
}
