"use client"

import Link from "next/link"
import * as AvatarPrimitive from "@radix-ui/react-avatar"
import { cva } from "class-variance-authority"

import type { VariantProps } from "class-variance-authority"
import type { ComponentProps, MouseEvent } from "react"

import { cn, getInitials } from "@/lib/utils"

import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"

export function Avatar({
  className,
  ...props
}: ComponentProps<typeof AvatarPrimitive.Root>) {
  return (
    <AvatarPrimitive.Root
      data-slot="avatar"
      className={cn("relative flex h-10 w-10 shrink-0", className)}
      {...props}
    />
  )
}

export function AvatarImage({
  className,
  ...props
}: ComponentProps<typeof AvatarPrimitive.Image>) {
  return (
    <AvatarPrimitive.Image
      data-slot="avatar-image"
      className={cn(
        "aspect-square h-full w-full bg-muted rounded-lg object-cover",
        className
      )}
      {...props}
    />
  )
}

export function AvatarFallback({
  className,
  ...props
}: ComponentProps<typeof AvatarPrimitive.Fallback>) {
  return (
    <AvatarPrimitive.Fallback
      className={cn(
        "flex h-full w-full items-center justify-center bg-muted rounded-lg",
        className
      )}
      {...props}
    />
  )
}

export const avatarStackVariants = cva(
  "transition duration-300 hover:scale-105 hover:z-10",
  {
    variants: {
      size: {
        default: "h-10 w-10",
        sm: "h-9 w-9 text-sm",
        lg: "h-11 w-11",
      },
    },
    defaultVariants: {
      size: "default",
    },
  }
)

interface AvatarStackProps
  extends ComponentProps<"div">,
    VariantProps<typeof avatarStackVariants> {
  avatars: { src?: string; alt: string; href?: string }[]
  avatarClassName?: string
  limit?: number
  onMoreButtonClick?: (event: MouseEvent<HTMLButtonElement>) => void
}

export function AvatarStack({
  avatars,
  limit = 4,
  size,
  onMoreButtonClick,
  className,
  avatarClassName,
  ...props
}: AvatarStackProps) {
  const limitedAvatars = avatars.slice(0, limit)
  const remainingCount = avatars.length - limitedAvatars.length

  return (
    <div className={cn("flex", className)} {...props}>
      {limitedAvatars.slice(0, limit).map((avatar) => (
        <TooltipProvider
          key={`${avatar.alt}-${avatar.src}`}
          delayDuration={200}
        >
          <Tooltip>
            <TooltipTrigger className="-ms-1 -me-1">
              {avatar.href ? (
                <Link href={avatar.href}>
                  <Avatar
                    className={cn(
                      avatarStackVariants({ size }),
                      avatarClassName
                    )}
                  >
                    <AvatarImage
                      src={avatar.src}
                      className="border-2 border-background"
                    />
                    <AvatarFallback className="border-2 border-background">
                      {getInitials(avatar.alt)}
                    </AvatarFallback>
                  </Avatar>
                </Link>
              ) : (
                <Avatar
                  className={cn(avatarStackVariants({ size }), avatarClassName)}
                >
                  <AvatarImage
                    src={avatar.src}
                    className="border-2 border-background"
                  />
                  <AvatarFallback className="border-2 border-background">
                    {getInitials(avatar.alt)}
                  </AvatarFallback>
                </Avatar>
              )}
            </TooltipTrigger>
            <TooltipContent className="capitalize -me-[1.23rem]">
              <p>{avatar.alt}</p>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      ))}

      {/* Show "+N" button if avatars exceed the limit */}
      {remainingCount > 0 && (
        <button
          type="button"
          onClick={onMoreButtonClick}
          className="-ms-1 -me-1"
          aria-label="Show more"
        >
          <Avatar
            className={cn(avatarStackVariants({ size }), avatarClassName)}
          >
            <AvatarFallback className="border-2 border-background">
              +{remainingCount}
            </AvatarFallback>
          </Avatar>
        </button>
      )}
    </div>
  )
}
