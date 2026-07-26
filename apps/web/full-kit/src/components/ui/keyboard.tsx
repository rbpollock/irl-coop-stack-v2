import type { ComponentProps } from "react"

import { cn } from "@/lib/utils"

export function Keyboard({
  className,
  children,
  ...props
}: ComponentProps<"kbd">) {
  return (
    <kbd
      data-slot="keyboard"
      className={cn(
        "pointer-events-none select-none h-5 inline-flex items-center gap-x-1 px-1.5 bg-muted text-sm text-muted-foreground font-mono border rounded-sm",
        "before:content-['⌘']",
        className
      )}
      {...props}
    >
      {children}
    </kbd>
  )
}
