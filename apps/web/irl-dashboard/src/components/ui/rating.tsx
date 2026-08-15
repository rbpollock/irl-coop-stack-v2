"use client"

import { useState } from "react"
import * as RadioGroupPrimitive from "@radix-ui/react-radio-group"
import { cva } from "class-variance-authority"

import type { DynamicIconNameType } from "@/types"
import type { VariantProps } from "class-variance-authority"
import type { ComponentPropsWithoutRef } from "react"

import { cn } from "@/lib/utils"

import { DynamicIcon } from "../dynamic-icon"

export const starVariants = cva(
  "transition-all duration-100 ease-in-out hover:scale-110",
  {
    variants: {
      size: {
        sm: "w-4 h-4",
        default: "w-6 h-6",
        lg: "w-8 h-8",
      },
      variant: {
        default: "text-yellow-400",
        primary: "text-primary",
        muted: "text-muted-foreground",
      },
      filled: {
        true: "",
        false: "text-gray-200",
      },
    },
    defaultVariants: {
      size: "default",
      variant: "default",
      filled: false,
    },
  }
)

interface RatingProps
  extends ComponentPropsWithoutRef<typeof RadioGroupPrimitive.Root>,
    VariantProps<typeof starVariants> {
  length?: number
  readOnly?: boolean
  iconName?: DynamicIconNameType
}

export function Rating({
  className,
  length = 5,
  size,
  variant = "default",
  orientation = "horizontal",
  readOnly = false,
  iconName = "Star",
  ...props
}: RatingProps) {
  const currentValue = props.value || "0"
  const [hoverValue, onHoverValue] = useState(currentValue)

  if (readOnly) {
    return (
      <div
        data-slot="rating"
        role="img"
        className={cn(
          "flex",
          orientation === "horizontal" ? "gap-x-1.5" : "flex-col space-y-1.5",
          className
        )}
        aria-label={`Rating: ${currentValue} out of ${length}`}
        {...props}
      >
        {Array.from({ length }, (_, index) => {
          const starValue = (index + 1).toString()
          const filled = Number(starValue) <= Number(currentValue)

          return (
            <DynamicIcon
              key={starValue}
              name={iconName}
              className={cn(
                starVariants({ size, variant, filled }),
                "fill-current"
              )}
              aria-hidden
            />
          )
        })}
      </div>
    )
  }

  return (
    <RadioGroupPrimitive.Root
      data-slot="rating"
      className={cn(
        "flex",
        orientation === "horizontal" ? "gap-x-1.5" : "flex-col space-y-1.5",
        className
      )}
      orientation={orientation}
      onMouseLeave={() => onHoverValue("0")}
      aria-label="Rating"
      {...props}
    >
      {Array.from({ length }).map((_, index) => {
        const starValue = (index + 1).toString()
        const filled =
          Number(starValue) <= (Number(hoverValue) || Number(currentValue))

        return (
          <RatingStar
            key={starValue}
            variant={variant}
            size={size}
            filled={filled}
            value={starValue}
            onHoverValue={onHoverValue}
            iconName={iconName}
          />
        )
      })}
    </RadioGroupPrimitive.Root>
  )
}

interface RatingStarProps
  extends RadioGroupPrimitive.RadioGroupItemProps,
    VariantProps<typeof starVariants> {
  onHoverValue: (rating: string) => void
  iconName: DynamicIconNameType
}

export function RatingStar({
  value,
  size,
  variant,
  filled,
  onHoverValue,
  iconName,
  ...props
}: RatingStarProps) {
  return (
    <RadioGroupPrimitive.Item
      data-slot="rating-star"
      value={value}
      className={cn(
        starVariants({ size, variant, filled }),
        "cursor-pointer focus:outline-hidden focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
      )}
      onMouseEnter={() => onHoverValue(value)}
      aria-label={`Rate ${value} star${value === "1" ? "" : "s"}`}
      {...props}
    >
      <DynamicIcon name={iconName} className="h-full w-full fill-current" />
    </RadioGroupPrimitive.Item>
  )
}
