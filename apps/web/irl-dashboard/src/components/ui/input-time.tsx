"use client"

import { useState } from "react"

import type { ChangeEvent, ComponentProps } from "react"

import { cn } from "@/lib/utils"

import { Input } from "./input"

export interface InputTimeProps extends ComponentProps<"input"> {
  onValueChange?: (value?: string) => void
}

export function InputTime({
  className,
  onValueChange,
  ...props
}: InputTimeProps) {
  const [isEmpty, setIsEmpty] = useState(!props.defaultValue && !props.value)

  const handleChange = (e: ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value

    setIsEmpty(!value)
    onValueChange?.(value)
  }

  return (
    <Input
      data-slot="input-time"
      className={cn(
        "block [&::-webkit-calendar-picker-indicator]:hidden rtl:text-right",
        isEmpty && "text-muted-foreground",
        className
      )}
      {...props}
      type="time"
      onChange={handleChange}
    />
  )
}
