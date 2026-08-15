"use client"

import { format } from "date-fns"
import { CalendarIcon } from "lucide-react"

import type { ComponentProps } from "react"
import type { DateRange } from "react-day-picker"

import { cn } from "@/lib/utils"

import { Button } from "@/components/ui/button"
import { Calendar } from "@/components/ui/calendar"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"

type DateRangePickerProps = Omit<
  ComponentProps<typeof Calendar>,
  "mode" | "selected" | "onSelect"
> & {
  value?: DateRange
  onValueChange?: (date?: DateRange) => void
  formatStr?: string
  popoverContentClassName?: string
  popoverContentOptions?: ComponentProps<typeof PopoverContent>
  buttonClassName?: string
  buttonOptions?: ComponentProps<typeof Button>
  placeholder?: string
}

export function DateRangePicker({
  value,
  onValueChange,
  formatStr = "yyyy-MM-dd",
  popoverContentClassName,
  popoverContentOptions,
  buttonClassName,
  buttonOptions,
  placeholder = "Pick date",
  ...props
}: DateRangePickerProps) {
  return (
    <Popover modal>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          className={cn("w-full px-3 text-start font-normal", buttonClassName)}
          {...buttonOptions}
        >
          {value?.from ? (
            value.to ? (
              <span>
                {format(value.from, formatStr)} to {format(value.to, formatStr)}
              </span>
            ) : (
              <span>{format(value.from, formatStr)}</span>
            )
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
          mode="range"
          selected={value}
          onSelect={onValueChange}
          {...props}
        />
      </PopoverContent>
    </Popover>
  )
}
