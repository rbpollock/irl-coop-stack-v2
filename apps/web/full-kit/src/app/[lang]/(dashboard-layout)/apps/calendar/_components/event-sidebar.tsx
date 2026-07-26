"use client"

import { useEffect } from "react"
import { zodResolver } from "@hookform/resolvers/zod"
import { useForm } from "react-hook-form"
import { CalendarCheck2, CalendarMinus } from "lucide-react"

import type { EventSidebarFormType, EventWithoutIdType } from "../types"

import { EventSidebarSchema } from "../_schemas/event-sidebar-schema"

import { useCalendarContext } from "../_hooks/calendar-context"
import { ButtonLoading } from "@/components/ui/button"
import { DatePicker } from "@/components/ui/date-picker"
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { Switch } from "@/components/ui/switch"
import { Textarea } from "@/components/ui/textarea"

export function EventSidebar() {
  const {
    calendarState,
    calendarApi,
    handleAddEvent,
    handleUpdateEvent,
    handleDeleteEvent,
    handleSelectEvent,
    eventSidebarIsOpen,
    setEventSidebarIsOpen,
  } = useCalendarContext()

  const form = useForm<EventSidebarFormType>({
    resolver: zodResolver(EventSidebarSchema),
    defaultValues: {
      title: "",
      url: "",
      description: "",
      allDay: true,
      start: new Date(),
      end: new Date(),
      category: "Miscellaneous",
    },
  })

  const { isSubmitting, isDirty } = form.formState
  const isDisabled = isSubmitting || !isDirty // Disable button if form is unchanged or submitting
  const selectedEvent = calendarState.selectedEvent

  // Reset the form with the current selected event's values if it exists; otherwise reset to the default state. This runs whenever `selectedEvent` or `eventSidebarIsOpen` changes
  useEffect(() => {
    if (selectedEvent) {
      const { extendedProps, ...eventProps } = selectedEvent

      form.reset({
        title: eventProps.title || "",
        url: eventProps.url || "",
        description: extendedProps.description || "",
        category: extendedProps.category || "Miscellaneous",
        start: eventProps.start || new Date(),
        end: eventProps.end || new Date(),
        allDay: eventProps.allDay ?? true,
      })
    } else {
      form.reset({
        url: "",
        title: "",
        description: "",
        allDay: true,
        start: new Date(),
        end: new Date(),
        category: "Miscellaneous",
      })
    }
  }, [eventSidebarIsOpen, selectedEvent, form])

  const handleSidebarClose = () => {
    handleSelectEvent(undefined) // Unselect the current event
    setEventSidebarIsOpen(false) // Close the sidebar
  }

  function onSubmit(data: EventSidebarFormType) {
    if (!calendarApi) return // Ensure the calendar API is available before proceeding

    const event: EventWithoutIdType = {
      ...(data.url && { url: data.url }), // Optional URL
      title: data.title,
      allDay: data.allDay,
      start: data.start,
      end: data.end,
      extendedProps: {
        description: data.description,
        category: data.category,
      },
    }

    if (selectedEvent) {
      handleUpdateEvent({
        id: selectedEvent.id, // Use the ID of the currently selected event
        ...event,
      })
    } else {
      handleAddEvent(event)
    }

    // Refresh the calendar and close the sidebar
    calendarApi.refetchEvents()
    handleSidebarClose()
  }

  function handleOnDeleteEvent() {
    if (!calendarApi) return // Ensure the calendar API is available before proceeding

    // Check if an event is currently selected
    if (selectedEvent) {
      handleDeleteEvent(selectedEvent.id) // Delete the event

      // Refresh the calendar and close the sidebar
      calendarApi.refetchEvents()
      handleSidebarClose()
    }
  }

  return (
    <Sheet open={eventSidebarIsOpen} onOpenChange={() => handleSidebarClose()}>
      <SheetContent className="p-0">
        <ScrollArea className="h-full p-4">
          <SheetHeader>
            <SheetTitle>
              {selectedEvent ? "Update Event" : "Add New Event"}
            </SheetTitle>
            <SheetDescription>
              {selectedEvent
                ? "Update the details of the selected event."
                : "Add a new event to your calendar."}
            </SheetDescription>
          </SheetHeader>
          <Form {...form}>
            <form
              onSubmit={form.handleSubmit(onSubmit)}
              className="grid gap-y-3 mt-3"
            >
              <FormField
                control={form.control}
                name="title"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Title</FormLabel>
                    <FormControl>
                      <Input placeholder="Event title" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="url"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>URL</FormLabel>
                    <FormControl>
                      <Input placeholder="https://example.com" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="category"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Category</FormLabel>
                    <Select
                      onValueChange={field.onChange}
                      defaultValue={field.value}
                    >
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder="Select a category" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        <SelectItem value="Business">Business</SelectItem>
                        <SelectItem value="Personal">Personal</SelectItem>
                        <SelectItem value="Family">Family</SelectItem>
                        <SelectItem value="Holiday">Holiday</SelectItem>
                        <SelectItem value="Health">Health</SelectItem>
                        <SelectItem value="Miscellaneous">
                          Miscellaneous
                        </SelectItem>
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="start"
                render={({ field }) => (
                  <FormItem className="flex flex-col">
                    <FormLabel>Start Date</FormLabel>
                    <FormControl>
                      <DatePicker
                        formatStr="PPP"
                        onValueChange={field.onChange}
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="end"
                render={({ field }) => (
                  <FormItem className="flex flex-col">
                    <FormLabel>End Date</FormLabel>
                    <FormControl>
                      <DatePicker
                        formatStr="PPP"
                        onValueChange={field.onChange}
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="allDay"
                render={({ field }) => (
                  <FormItem className="flex flex-row items-center justify-between rounded-lg border p-4">
                    <div className="space-y-0.5">
                      <FormLabel className="text-base">All Day</FormLabel>
                      <FormDescription>
                        Is this an all-day event?
                      </FormDescription>
                    </div>
                    <FormControl>
                      <Switch
                        checked={field.value}
                        onCheckedChange={field.onChange}
                      />
                    </FormControl>
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="description"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Description</FormLabel>
                    <FormControl>
                      <Textarea
                        placeholder="Event description"
                        className="resize-none"
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <ButtonLoading
                isLoading={isSubmitting}
                disabled={isDisabled}
                className="w-full"
                icon={CalendarCheck2}
              >
                Save
              </ButtonLoading>

              {/* Display the delete button only when an event is selected to avoid showing it during event creation */}
              {selectedEvent && (
                <ButtonLoading
                  isLoading={isSubmitting}
                  variant="destructive"
                  className="w-full"
                  onClick={handleOnDeleteEvent}
                  icon={CalendarMinus}
                >
                  Delete
                </ButtonLoading>
              )}
            </form>
          </Form>
        </ScrollArea>
      </SheetContent>
    </Sheet>
  )
}
