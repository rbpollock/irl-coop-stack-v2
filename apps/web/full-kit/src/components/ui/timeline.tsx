import { Slot } from "@radix-ui/react-slot"
import { cva } from "class-variance-authority"

import type { DynamicIconNameType } from "@/types"
import type * as SeparatorPrimitive from "@radix-ui/react-separator"
import type { VariantProps } from "class-variance-authority"
import type { ComponentProps } from "react"

import { cn } from "@/lib/utils"

import { DynamicIcon } from "../dynamic-icon"
import { Separator } from "./separator"

export const timelineVariants = cva("grid", {
  variants: {
    align: {
      left: "[&>li]:grid-cols-[0_min-content_1fr]",
      right: "[&>li]:grid-cols-[1fr_min-content]",
      center: "[&>li]:grid-cols-[1fr_min-content_1fr]",
    },
  },
  defaultVariants: {
    align: "left",
  },
})

type TimelineProps = ComponentProps<"ul"> &
  VariantProps<typeof timelineVariants>

export function Timeline({
  children,
  className,
  align,
  ...props
}: TimelineProps) {
  return (
    <ul
      data-slot="timeline"
      className={cn(timelineVariants({ align }), className)}
      {...props}
    >
      {children}
    </ul>
  )
}

export const timelineItemVariants = cva("grid items-center gap-x-2", {
  variants: {
    status: {
      done: "text-foreground",
      default: "text-muted-foreground",
    },
  },
  defaultVariants: {
    status: "default",
  },
})

type TimelineItemProps = ComponentProps<"li"> &
  VariantProps<typeof timelineItemVariants>

export function TimelineItem({
  className,
  status,
  ...props
}: TimelineItemProps) {
  return (
    <li
      data-slot="timeline-item"
      className={cn(timelineItemVariants({ status }), className)}
      {...props}
    />
  )
}

type TimelineDotStatus = "current" | "done" | "error"

interface TimelineDotPropsBase extends ComponentProps<"div"> {
  iconClassName?: string
}

interface TimelineDotPropsWithStatus extends TimelineDotPropsBase {
  status?: TimelineDotStatus
  customIconName?: never
  customStatusName?: never
}

interface TimelineDotPropsWithCustom extends TimelineDotPropsBase {
  status?: never
  customIconName: DynamicIconNameType
  customStatusName: string
}

type TimelineDotProps = TimelineDotPropsWithStatus | TimelineDotPropsWithCustom

type StatusIconNamesType = Record<
  TimelineDotStatus,
  { iconName: DynamicIconNameType; className: string }
>

const statusIconNames: StatusIconNamesType = {
  current: {
    iconName: "Circle",
    className: "fill-foreground text-foreground rounded-full",
  },
  done: {
    iconName: "Check",
    className: "bg-primary text-primary-foreground p-0.5 rounded-full",
  },
  error: {
    iconName: "X",
    className: "bg-destructive text-destructive-foreground p-0.5 rounded-full",
  },
}

export function TimelineDot({
  className,
  iconClassName,
  status = "current",
  customIconName,
  customStatusName,
  ...props
}: TimelineDotProps) {
  let statusIconName = statusIconNames["current"].iconName
  let statusLabel = "current"
  let statusClassName

  // Determines if the component uses predefined statuses or custom ones
  if (customStatusName && customIconName) {
    // If a custom icon is provided, use it along with the custom status label
    statusIconName = customIconName
    statusLabel = customStatusName
  } else if (status) {
    // If the "status" prop exists, use the corresponding predefined icon and styling
    statusIconName = statusIconNames[status].iconName
    statusClassName = statusIconNames[status].className
    statusLabel = status // Assigns the status label for accessibility
  }

  return (
    <div
      data-slot="timeline-dot"
      role="status"
      className={cn(
        "col-start-2 col-end-3 row-start-1 row-end-1 flex justify-center items-center rounded-md",
        className
      )}
      aria-label={statusLabel}
      {...props}
    >
      <DynamicIcon
        name={statusIconName}
        className={cn(
          "size-4 text-muted-foreground",
          statusClassName,
          iconClassName
        )}
      />
    </div>
  )
}

export const timelineContentVariants = cva("row-start-2 row-end-2 pb-8", {
  variants: {
    side: {
      start: "col-start-3 col-end-4 me-auto text-start",
      end: "col-start-1 col-end-2 ms-auto text-end",
    },
  },
  defaultVariants: {
    side: "start",
  },
})

type TimelineContentProps = ComponentProps<"div"> &
  VariantProps<typeof timelineContentVariants>

export function TimelineContent({
  className,
  side,
  ...props
}: TimelineContentProps) {
  return (
    <div
      data-slot="timeline-content"
      className={cn(timelineContentVariants({ side }), className)}
      {...props}
    />
  )
}

export const timelineHeadingVariants = cva(
  "row-start-1 row-end-1 line-clamp-1 max-w-full truncate",
  {
    variants: {
      side: {
        start: "col-start-3 col-end-4 me-auto text-start",
        end: "col-start-1 col-end-2 ms-auto text-end",
      },
      variant: {
        primary: "text-base font-medium text-foreground",
        secondary: "text-sm font-light text-muted-foreground",
      },
    },
    defaultVariants: {
      side: "start",
      variant: "primary",
    },
  }
)

type TimelineHeadingProps = ComponentProps<"h3"> &
  VariantProps<typeof timelineHeadingVariants> & {
    asChild?: boolean
  }

export function TimelineHeading({
  className,
  side,
  variant,
  asChild = false,
  ...props
}: TimelineHeadingProps) {
  const Comp = asChild ? Slot : "h3"

  return (
    <Comp
      data-slot="timeline-heading"
      className={cn(timelineHeadingVariants({ side, variant }), className)}
      {...props}
    />
  )
}

type TimelineLineProps = ComponentProps<typeof SeparatorPrimitive.Root> & {
  done?: boolean
}

export function TimelineLine({
  className,
  done = false,
  ...props
}: TimelineLineProps) {
  return (
    <Separator
      data-slot="timeline-line"
      orientation="vertical"
      className={cn(
        "col-start-2 col-end-3 row-start-2 row-end-2 bg-muted-foreground mx-auto w-[0.094rem]",
        done && "bg-foreground",
        className
      )}
      {...props}
    />
  )
}
