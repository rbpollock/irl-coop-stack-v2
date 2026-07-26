"use client"

import { useState } from "react"
import { CalendarPlus, ChevronLeft, ChevronRight } from "lucide-react"

import { useCalendarContext } from "../_hooks/calendar-context"
import { Button } from "@/components/ui/button"
import { CardHeader } from "@/components/ui/card"
import { INITIAL_VIEW } from "../constants"
import { EventFilters } from "./event-filters"

export function CalendarHeader() {
  const { calendarApi, setEventSidebarIsOpen } = useCalendarContext()
  const [currentView, setCurrentView] = useState(INITIAL_VIEW)
  const [currentDate, setCurrentDate] = useState<Date>(new Date())

  // Function to navigate to a specific date on the calendar and update the current date state
  const handleDateChange = (newDate: Date) => {
    if (calendarApi) {
      calendarApi.gotoDate(newDate) // Move the calendar to the given date
      setCurrentDate(newDate) // Update the current date state
    }
  }

  // Function to move the calendar view to the previous period (e.g., previous month)
  const handlePrev = () => {
    if (calendarApi) {
      calendarApi.prev() // Move to the previous date range
      handleDateChange(calendarApi.getDate()) // Update the current date state after moving
    }
  }

  // Function to move the calendar view to the next period (e.g., next month)
  const handleNext = () => {
    if (calendarApi) {
      calendarApi.next() // Move to the next date range
      handleDateChange(calendarApi.getDate()) // Update the current date state after moving
    }
  }

  // Function to change the view mode (e.g., day, week, month, list) of the calendar
  const handleViewChange = (view: string) => {
    if (calendarApi) {
      calendarApi.changeView(view) // Change the view mode
      handleDateChange(calendarApi.getDate()) // Update the current date state after changing views
      setCurrentView(view) // Update the current view state
    }
  }

  // Function to format the title based on the current date and view mode
  const formatTitle = (date: Date, view: string) => {
    if (view === "dayGridMonth") {
      // For month view, display the year and month
      return date.toLocaleDateString("en-US", {
        year: "numeric",
        month: "long",
      })
    } else if (view === "timeGridWeek" || view === "listWeek") {
      // For week view, display the range from the start of the week to the end
      const endDate = new Date(date)
      endDate.setDate(endDate.getDate() + 6) // Calculate the end date (7 days from start)
      return `${date.toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
      })} - ${endDate.toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
      })}`
    } else {
      // For day view, display the full date (weekday, month, day, year)
      return date.toLocaleDateString("en-US", {
        weekday: "long",
        year: "numeric",
        month: "long",
        day: "numeric",
      })
    }
  }

  return (
    <CardHeader className="justify-between items-center gap-4 space-y-0 md:flex-row">
      <div className="flex flex-wrap-reverse justify-center items-center gap-4">
        <div className="flex gap-x-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setEventSidebarIsOpen(true)}
            aria-label="Add new event"
          >
            <CalendarPlus className="h-4 w-4" />
          </Button>
          <EventFilters />
          <Button
            variant="outline"
            size="sm"
            onClick={handlePrev}
            aria-label="Previous month"
          >
            <ChevronLeft className="h-4 w-4 rtl:-scale-100" />
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={handleNext}
            aria-label="Next month"
          >
            <ChevronRight className="h-4 w-4 rtl:-scale-100" />
          </Button>
        </div>
        <h2 className="text-lg font-semibold">
          {formatTitle(currentDate, currentView)}
        </h2>
      </div>
      <div className="flex gap-x-2">
        <Button
          variant={currentView === "dayGridMonth" ? "default" : "outline"} // Default variant when it's the active view; otherwise, outline for non-active views
          size="sm"
          onClick={() => handleViewChange("dayGridMonth")}
        >
          Month
        </Button>
        <Button
          variant={currentView === "timeGridWeek" ? "default" : "outline"} // Default variant when it's the active view; otherwise, outline for non-active views
          size="sm"
          onClick={() => handleViewChange("timeGridWeek")}
        >
          Week
        </Button>
        <Button
          variant={currentView === "timeGridDay" ? "default" : "outline"} // Default variant when it's the active view; otherwise, outline for non-active views
          size="sm"
          onClick={() => handleViewChange("timeGridDay")}
        >
          Day
        </Button>
        <Button
          variant={currentView === "listWeek" ? "default" : "outline"} // Default variant when it's the active view; otherwise, outline for non-active views
          size="sm"
          onClick={() => handleViewChange("listWeek")}
        >
          List
        </Button>
      </div>
    </CardHeader>
  )
}
