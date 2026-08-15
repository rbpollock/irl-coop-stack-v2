"use client"

import { useState } from "react"
import { format } from "date-fns"
import { CalendarIcon } from "lucide-react"

import type { ComponentProps } from "react"

import { cn } from "@/lib/utils"

import { Button } from "@/components/ui/button"
import { Calendar } from "@/components/ui/calendar"
import { InputTime } from "@/components/ui/input-time"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import { Separator } from "@/components/ui/separator"

type DateTimePickerProps = Omit<
  ComponentProps<typeof Calendar>,
  "mode" | "selected" | "onSelect"
> & {
  value?: Date
  onValueChange?: (date?: Date) => void
  formatStr?: string
  popoverContentClassName?: string
  popoverContentOptions?: ComponentProps<typeof PopoverContent>
  buttonClassName?: string
  buttonOptions?: ComponentProps<typeof Button>
  placeholder?: string
}

export function DateTimePicker({
  value,
  onValueChange,
  formatStr = "yyyy-MM-dd p",
  popoverContentClassName,
  popoverContentOptions,
  buttonClassName,
  buttonOptions,
  placeholder = "Pick date and time",
  ...props
}: DateTimePickerProps) {
  const [selectedDate, setSelectedDate] = useState<Date | undefined>(value)

  const handleDateSelect = (selected?: Date | undefined) => {
    if (!selected) return

    // Preserve the time when changing the date
    const newDateTime = new Date(selected)
    if (selectedDate) {
      newDateTime.setHours(selectedDate.getHours())
      newDateTime.setMinutes(selectedDate.getMinutes())
    }

    setSelectedDate(newDateTime)
    onValueChange?.(newDateTime)
  }

  const handleTimeChange = (timeString?: string) => {
    if (!timeString) return

    const [hours, minutes] = timeString.split(":").map(Number)

    if (selectedDate) {
      const newDateTime = new Date(selectedDate)
      newDateTime.setHours(hours)
      newDateTime.setMinutes(minutes)

      setSelectedDate(newDateTime)
      onValueChange?.(newDateTime)
    }
  }

  return (
    <Popover modal>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          className={cn("w-full px-3 text-start font-normal", buttonClassName)}
          {...buttonOptions}
        >
          {selectedDate ? (
            <span>{format(selectedDate, formatStr)}</span>
          ) : (
            <span className="text-muted-foreground">{placeholder}</span>
          )}
          <CalendarIcon className="ms-auto h-4 w-4 text-muted-foreground" />
        </Button>
      </PopoverTrigger>
      <PopoverContent
        className={cn("w-auto p-0", popoverContentClassName)}
        align="start"
        {...popoverContentOptions}
      >
        <Calendar
          mode="single"
          selected={selectedDate}
          onSelect={handleDateSelect}
          {...props}
        />
        <Separator />
        <InputTime
          className="rounded-t-none border-0"
          onValueChange={handleTimeChange}
          value={selectedDate ? format(selectedDate, "p") : undefined}
        />
      </PopoverContent>
    </Popover>
  )
}
