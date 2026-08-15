"use client"

import { format } from "date-fns"
import { CalendarIcon } from "lucide-react"

import type { ComponentProps } from "react"

import { cn } from "@/lib/utils"

import { Button } from "@/components/ui/button"
import { Calendar } from "@/components/ui/calendar"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"

type DatePickerProps = Omit<
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

export function DatePicker({
  value,
  onValueChange,
  formatStr = "yyyy-MM-dd",
  popoverContentClassName,
  popoverContentOptions,
  buttonClassName,
  buttonOptions,
  placeholder = "Pick date",
  ...props
}: DatePickerProps) {
  return (
    <Popover modal>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          className={cn("w-full px-3 text-start font-normal", buttonClassName)}
          {...buttonOptions}
        >
          {value ? (
            <span>{format(value, formatStr)}</span>
          ) : (
            <span className="text-muted-foreground">{placeholder}</span>
          )}
          <CalendarIcon className="shrink-0 h-4 w-4 ms-auto text-muted-foreground" />
        </Button>
      </PopoverTrigger>
      <PopoverContent
        className={cn("w-auto p-0", popoverContentClassName)}
        align="start"
        {...popoverContentOptions}
      >
        <Calendar
          mode="single"
          selected={value}
          onSelect={onValueChange}
          {...props}
        />
      </PopoverContent>
    </Popover>
  )
}
