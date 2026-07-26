// Refer to FullCalendar documentation for more details https://fullcalendar.io/docs
"use client"

import { useEffect, useRef } from "react"
import dayGridPlugin from "@fullcalendar/daygrid"
import interactionPlugin from "@fullcalendar/interaction"
import listPlugin from "@fullcalendar/list"
import FullCalendar from "@fullcalendar/react"
import timeGridPlugin from "@fullcalendar/timegrid"
import { useDirection } from "@radix-ui/react-direction"

import type { DateInput, EventSourceInput } from "@fullcalendar/core/index.js"
import type { EventImpl } from "@fullcalendar/core/internal"
import type { CategoryType, EventType } from "../types"

import { useCalendarContext } from "../_hooks/calendar-context"
import { INITIAL_VIEW } from "../constants"

const eventColors: Record<CategoryType, string> = {
  Business: "hsl(var(--chart-1))",
  Personal: "hsl(var(--chart-2))",
  Family: "hsl(var(--chart-3))",
  Holiday: "hsl(var(--chart-4))",
  Health: "hsl(var(--chart-5))",
  Miscellaneous: "hsl(var(--primary))",
}

export function CalendarContent() {
  const direction = useDirection()
  const {
    calendarState,
    calendarApi,
    setCalendarApi,
    handleSelectEvent,
    handleUpdateEvent,
    setEventSidebarIsOpen,
  } = useCalendarContext()

  const calendarRef = useRef<null | FullCalendar>(null)

  // Initialize the calendar API when the component mounts or when `calendarApi` is not already set
  useEffect(() => {
    if (!calendarApi && calendarRef.current) {
      setCalendarApi(calendarRef.current.getApi())
    }
  }, [calendarApi, setCalendarApi])

  // Function to parse and transform an event from FullCalendar's internal event representation to a structured format
  const parseEvent = (event: EventImpl): EventType => {
    return {
      id: event.id,
      ...(event.url && { url: event.url }), // Include URL property if it exists
      title: event.title,
      allDay: event.allDay,
      start: event.start || new Date(),
      end: event.end || event.start || new Date(),
      extendedProps: {
        category: event.extendedProps.category,
        ...(event.extendedProps.description && {
          description: event.extendedProps.description,
        }), // Include description if it exists in the extended properties
      },
    }
  }

  const handleDateClick = (date: DateInput) => {
    if (calendarApi) {
      calendarApi.changeView("timeGridDay", date)
    }
  }

  const handleEventDrop = ({ event }: { event: EventImpl }) => {
    return handleUpdateEvent(parseEvent(event))
  }

  const handleEventResize = ({ event }: { event: EventImpl }) => {
    return handleUpdateEvent(parseEvent(event))
  }

  const handleEventClick = ({
    event,
    jsEvent,
  }: {
    event: EventImpl
    jsEvent: MouseEvent
  }) => {
    jsEvent.preventDefault() // Prevent default behavior like following a link

    handleSelectEvent(parseEvent(event))
    setEventSidebarIsOpen(true)
  }

  // Map events from the state and assign a color based on their category
  const events = calendarState.events.map(
    (event: EventType): EventSourceInput[] => ({
      ...event,
      // @ts-ignore
      color: eventColors[event.extendedProps.category], // Set color based on event category
    })
  )

  // Custom class names for event styling
  const eventClassNames = () => [
    "h-[1.62rem] pt-px px-1 rounded-md",
    "hover:[&_td]:bg-accent/60!", // Styling for hover state on table cells
  ]

  return (
    <FullCalendar
      ref={calendarRef}
      direction={direction}
      initialView={INITIAL_VIEW}
      plugins={[dayGridPlugin, timeGridPlugin, interactionPlugin, listPlugin]}
      eventDisplay="block"
      events={events}
      eventClassNames={eventClassNames}
      headerToolbar={false}
      editable
      eventResizableFromStart
      dragScroll
      dayMaxEvents={2}
      height="auto"
      navLinks
      navLinkDayClick={handleDateClick}
      eventDrop={handleEventDrop}
      eventResize={handleEventResize}
      eventClick={handleEventClick}
    />
  )
}
