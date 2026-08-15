"use client"

import type { ComponentProps } from "react"

import { cn } from "@/lib/utils"

export interface InputGroupProps extends ComponentProps<"div"> {}

export function InputGroup({ className, children, ...props }: InputGroupProps) {
  return (
    <div
      data-slot="input-group"
      className={cn(
        "flex min-h-9 w-full rounded-md border border-input bg-transparent text-sm transition-colors [&>*:not(.input-group-text)]:border-0 [&>input]:z-10 [&>input]:first:rounded-e-none [&>input]:last:rounded-s-none [&>input:not(:first-child):not(:last-child)]:rounded-none [&>textarea]:z-10 [&>textarea]:first:rounded-e-none [&>textarea]:last:rounded-s-none [&>textarea:not(:first-child):not(:last-child)]:rounded-none [&>button]:first:rounded-e-none [&>button]:last:rounded-s-none [&>button]:[&:not(:first-child):not(:last-child)]:rounded-none",
        className
      )}
      {...props}
    >
      {children}
    </div>
  )
}

export interface InputGroupTextProps extends ComponentProps<"div"> {
  merged?: boolean
}

export function InputGroupText({
  className,
  merged = false,
  ...props
}: InputGroupTextProps) {
  return (
    <div
      data-slot="input-group-text"
      className={cn(
        "input-group-text",
        "flex items-center justify-center border-input px-3 py-1 text-sm text-muted-foreground",
        !merged &&
          "first:rounded-s-md last:rounded-e-md first:border-e last:border-s [&:not(:first-child):not(:last-child)]:border-x",
        className
      )}
      {...props}
    />
  )
}
