import Link from "next/link"
import { ChevronLeft, ChevronRight, MoreHorizontal } from "lucide-react"

import type { Button } from "@/components/ui/button"
import type { ComponentProps } from "react"

import { cn } from "@/lib/utils"

import { buttonVariants } from "@/components/ui/button"

export function Pagination({ className, ...props }: ComponentProps<"nav">) {
  return (
    <nav
      data-slot="pagination"
      role="navigation"
      className={cn("mx-auto flex w-full justify-center", className)}
      aria-label="pagination"
      {...props}
    />
  )
}

export function PaginationContent({
  className,
  ...props
}: ComponentProps<"ul">) {
  return (
    <ul
      data-slot="pagination-content"
      className={cn("flex flex-row items-center gap-1", className)}
      {...props}
    />
  )
}

export function PaginationItem({ ...props }: ComponentProps<"li">) {
  return <li data-slot="pagination-item" {...props} />
}

export type PaginationLinkProps = {
  isActive?: boolean
} & Pick<ComponentProps<typeof Button>, "size"> &
  ComponentProps<typeof Link>

export function PaginationLink({
  className,
  isActive,
  size = "icon",
  href = "",
  ...props
}: PaginationLinkProps) {
  return (
    <Link
      data-slot="pagination-link"
      className={cn(
        buttonVariants({
          variant: isActive ? "outline" : "ghost",
          size,
        }),
        className
      )}
      href={href}
      aria-current={isActive ? "page" : undefined}
      {...props}
    />
  )
}

export function PaginationPrevious({
  className,
  ...props
}: ComponentProps<typeof PaginationLink>) {
  return (
    <PaginationLink
      size="default"
      className={cn("gap-1 ps-2.5", className)}
      aria-label="Go to previous page"
      {...props}
    >
      <ChevronLeft className="h-4 w-4 rtl:-scale-100" />
      <span>Previous</span>
    </PaginationLink>
  )
}

export function PaginationNext({
  className,
  ...props
}: ComponentProps<typeof PaginationLink>) {
  return (
    <PaginationLink
      size="default"
      className={cn("gap-1 pe-2.5", className)}
      aria-label="Go to next page"
      {...props}
    >
      <span>Next</span>
      <ChevronRight className="h-4 w-4 rtl:-scale-100" />
    </PaginationLink>
  )
}

export function PaginationEllipsis({
  className,
  ...props
}: ComponentProps<"span">) {
  return (
    <span
      data-slot="pagination-ellipsis"
      className={cn("flex h-9 w-9 items-center justify-center", className)}
      aria-label="More pages"
      aria-hidden
      {...props}
    >
      <MoreHorizontal className="h-4 w-4" />
    </span>
  )
}
