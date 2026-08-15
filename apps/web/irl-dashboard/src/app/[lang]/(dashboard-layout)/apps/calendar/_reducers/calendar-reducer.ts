import type {
  CalendarActionType,
  CalendarStateType,
  CategoryType,
  EventType,
} from "../types"

import { CATEGORIES } from "../constants"

export function CalendarReducer(
  calendarState: CalendarStateType,
  action: CalendarActionType
): CalendarStateType {
  switch (action.type) {
    case "addEvent": {
      return {
        ...calendarState,
        events: [...calendarState.events, action.event as EventType], // Add new event
      }
    }

    case "updateEvent": {
      const events = calendarState.events.map((event) => {
        // Update event if ID matches, else retain original
        return event.id === action.event?.id ? action.event : event
      })

      return {
        ...calendarState,
        events, // Update events array
      }
    }

    case "deleteEvent": {
      const events = calendarState.events.filter(
        (event) => event.id !== action.eventId // Remove event by ID
      )

      return {
        ...calendarState,
        events,
      }
    }

    case "selectEvent": {
      return {
        ...calendarState,
        selectedEvent: action.event, // Set selected event
      }
    }

    case "selectCategory": {
      const tempSelectedCategories = [...calendarState.selectedCategories]

      // Toggle category selection
      const index = tempSelectedCategories.indexOf(
        action.category as CategoryType
      )
      if (index !== -1) {
        tempSelectedCategories.splice(index, 1) // Remove category if already selected
      } else {
        tempSelectedCategories.push(action.category as CategoryType) // Add category if not selected
      }

      // Filter events based on selected categories
      const tempSelectedEvents = calendarState.initalEvents.filter((event) =>
        tempSelectedCategories.includes(
          event.extendedProps.category as CategoryType
        )
      )

      return {
        ...calendarState,
        events: tempSelectedEvents,
        selectedCategories: tempSelectedCategories,
      }
    }

    case "selectAllCategories": {
      let tempSelectedCategories = CATEGORIES
      let tempEvents = calendarState.initalEvents

      if (!action.isSelectAllCategories) {
        // Deselect all categories and clear events
        tempSelectedCategories = []
        tempEvents = []
      }

      return {
        ...calendarState,
        events: tempEvents,
        selectedCategories: tempSelectedCategories,
      }
    }

    default:
      return calendarState // Return the current state for unhandled action types
  }
}
