import type { EventType } from "../types"

export const eventsData: EventType[] = [
  {
    id: "1",
    title: "Team Meeting",
    allDay: true,
    start: new Date(new Date().setDate(new Date().getDate())),
    end: new Date(new Date().setDate(new Date().getDate())),
    extendedProps: {
      category: "Business",
      description: "Discuss project updates.",
    },
  },
  {
    id: "2",
    title: "Doctor Appointment",
    allDay: true,
    start: new Date(new Date().setDate(new Date().getDate() + 5)),
    end: new Date(new Date().setDate(new Date().getDate() + 5)),
    extendedProps: {
      category: "Health",
      description: "Annual check-up.",
    },
  },
  {
    id: "3",
    title: "Birthday Party",
    allDay: true,
    start: new Date(new Date().setDate(new Date().getDate() - 10)),
    end: new Date(new Date().setDate(new Date().getDate() - 10)),
    extendedProps: {
      category: "Family",
      description: "Celebrating John’s birthday.",
    },
  },
  {
    id: "4",
    title: "Project Deadline",
    allDay: true,
    start: new Date(new Date().setDate(new Date().getDate() + 15)),
    end: new Date(new Date().setDate(new Date().getDate() + 15)),
    extendedProps: {
      category: "Business",
      description: "Final submission for the project.",
    },
  },
  {
    id: "5",
    title: "Weekend Getaway",
    allDay: true,
    start: new Date(new Date().setDate(new Date().getDate() - 5)),
    end: new Date(new Date().setDate(new Date().getDate() - 3)),
    extendedProps: {
      category: "Holiday",
      description: "Relaxing at the beach.",
    },
  },
  {
    id: "6",
    title: "Family Reunion",
    allDay: true,
    start: new Date(new Date().setDate(new Date().getDate() + 25)),
    end: new Date(new Date().setDate(new Date().getDate() + 25)),
    extendedProps: {
      category: "Family",
      description: "Gathering with relatives.",
    },
  },
]
