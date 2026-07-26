import { Slot } from "@radix-ui/react-slot"

import type { ComponentProps } from "react"

import { cn } from "@/lib/utils"

export function BentoGrid({ className, ...props }: ComponentProps<"div">) {
  return (
    <div
      data-slot="bento-grid"
      className={cn("w-full grid gap-4 mx-auto md:grid-cols-3", className)}
      {...props}
    />
  )
}

export function BentoItem({ className, ...props }: ComponentProps<"div">) {
  return (
    <div
      data-slot="bento-item"
      className={cn(
        "group/bento flex flex-col justify-between gap-6 p-6 bg-card text-card-foreground rounded-lg border overflow-hidden",
        className
      )}
      {...props}
    />
  )
}

export function BentoHeader({ className, ...props }: ComponentProps<"div">) {
  return (
    <div
      data-slot="bento-header"
      className={cn("flex-1 w-full h-full select-none", className)}
      {...props}
    />
  )
}

export function BentoContent({ className, ...props }: ComponentProps<"div">) {
  return (
    <div
      data-slot="bento-content"
      className={cn("space-y-1.5", className)}
      {...props}
    />
  )
}

interface BentoTitleProps extends ComponentProps<"div"> {
  asChild?: boolean
}

export function BentoTitle({ className, asChild, ...props }: BentoTitleProps) {
  const Comp = asChild ? Slot : "h2"

  return (
    <Comp
      data-slot="bento-title"
      className={cn("font-semibold leading-none tracking-tight", className)}
      {...props}
    />
  )
}

export function BentoDescription({
  className,
  ...props
}: ComponentProps<"div">) {
  return (
    <p
      data-slot="bento-description"
      className={cn("text-sm text-muted-foreground", className)}
      {...props}
    />
  )
}
