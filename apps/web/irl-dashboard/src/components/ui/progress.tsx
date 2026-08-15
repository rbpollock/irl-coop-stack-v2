"use client"

import * as ProgressPrimitive from "@radix-ui/react-progress"

import type { ComponentProps } from "react"

import { cn } from "@/lib/utils"

export function Progress({
  className,
  value,
  max,
  ...props
}: ComponentProps<typeof ProgressPrimitive.Root>) {
  return (
    <ProgressPrimitive.Root
      data-slot="progress"
      className={cn(
        "relative h-2 w-full overflow-hidden rounded-lg bg-primary/20",
        className
      )}
      max={max}
      {...props}
    >
      <ProgressPrimitive.Indicator
        data-slot="progress-indicator"
        className="h-full w-full flex-1 bg-primary transition-all"
        style={{
          transform: `translateX(-${100 - ((value || 0) / (max || 100)) * 100}%)`,
        }}
      />
    </ProgressPrimitive.Root>
  )
}
