"use client"

import { useContext } from "react"

import { CalendarContext } from "../_contexts/calendar-context"

export function useCalendarContext() {
  const context = useContext(CalendarContext)
  if (context === undefined) {
    throw new Error("useCalendarContext must be used within a CalendarProvider")
  }
  return context
}
