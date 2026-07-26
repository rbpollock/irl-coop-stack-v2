import type { CalendarApi } from "@fullcalendar/core/index.js"
import type { z } from "zod"
import type { EventSidebarSchema } from "./_schemas/event-sidebar-schema"

export interface CalendarContextType {
  calendarState: CalendarStateType
  calendarApi: CalendarApi | null
  setCalendarApi: (val: CalendarApi) => void
  eventSidebarIsOpen: boolean
  setEventSidebarIsOpen: (val: boolean) => void
  handleAddEvent: (event: EventWithoutIdType) => void
  handleUpdateEvent: (event: EventType) => void
  handleDeleteEvent: (eventId: EventType["id"]) => void
  handleSelectEvent: (event?: EventType) => void
  handleSelectCategory: (category: CategoryType) => void
  handleSelectAllCategories: (isSelectAllCategories: boolean) => void
}

export type CategoryType =
  | "Business"
  | "Personal"
  | "Family"
  | "Holiday"
  | "Health"
  | "Miscellaneous"

export type EventType = {
  id: string
  url?: string
  title: string
  allDay: boolean
  end: Date
  start: Date
  extendedProps: {
    category: CategoryType
    description?: string
  }
}

export type EventWithoutIdType = Omit<EventType, "id">

export type CalendarStateType = {
  initalEvents: EventType[]
  events: EventType[]
  selectedEvent?: EventType
  selectedCategories: CategoryType[]
}

export type CalendarActionType = {
  type:
    | "addEvent"
    | "updateEvent"
    | "deleteEvent"
    | "selectEvent"
    | "selectCategory"
    | "selectAllCategories"
  event?: EventType
  category?: CategoryType
  eventId?: string
  isSelectAllCategories?: boolean
}

export type EventSidebarFormType = z.infer<typeof EventSidebarSchema>
