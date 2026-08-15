// Refer to emoji-picker-react README.md file for more details https://github.com/ealush/emoji-picker-react
"use client"

import dynamic from "next/dynamic"
import { Theme } from "emoji-picker-react"
import { Smile } from "lucide-react"

import type { Button } from "@/components/ui/button"
import type { ComponentProps, ComponentPropsWithoutRef } from "react"

import { cn } from "@/lib/utils"

import { useIsDarkMode } from "@/hooks/use-mode"
import { buttonVariants } from "@/components/ui/button"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"

// Avoid errors such as "document is not defined" on the server side
// See https://github.com/ealush/emoji-picker-react?tab=readme-ov-file#nextjs
const Picker = dynamic(
  () => {
    return import("emoji-picker-react")
  },
  { ssr: false }
)

interface EmojiPickerProps extends ComponentProps<typeof Picker> {
  popoverContentClassName?: string
  popoverContentOptions?: ComponentPropsWithoutRef<typeof PopoverContent>
  buttonClassName?: string
  buttonOptions?: ComponentProps<typeof Button>
  placeholder?: string
}

export function EmojiPicker({
  popoverContentClassName,
  popoverContentOptions,
  buttonClassName,
  buttonOptions,
  ...props
}: EmojiPickerProps) {
  const isDarkMode = useIsDarkMode()

  const theme = isDarkMode ? Theme.DARK : Theme.LIGHT

  return (
    <Popover>
      <PopoverTrigger
        className={cn(
          buttonVariants({ variant: "ghost", size: "icon" }),
          buttonClassName
        )}
        {...buttonOptions}
        aria-label="Emoji"
      >
        <Smile className="h-4 w-4" />
      </PopoverTrigger>
      <PopoverContent
        className={cn("w-auto p-0", popoverContentClassName)}
        align="start"
        {...popoverContentOptions}
      >
        <Picker theme={theme} searchPlaceholder="Search..." {...props} />
      </PopoverContent>
    </Popover>
  )
}

export function ReactionPicker({
  popoverContentClassName,
  popoverContentOptions,
  buttonClassName,
  buttonOptions,
  ...props
}: EmojiPickerProps) {
  const isDarkMode = useIsDarkMode()

  const theme = isDarkMode ? Theme.DARK : Theme.LIGHT

  return (
    <Popover>
      <PopoverTrigger
        className={cn(
          buttonVariants({ variant: "ghost", size: "icon" }),
          buttonClassName
        )}
        {...buttonOptions}
        aria-label="Emoji"
      >
        <Smile className="h-4 w-4" />
      </PopoverTrigger>
      <PopoverContent
        className={cn("w-auto p-0", popoverContentClassName)}
        align="start"
        {...popoverContentOptions}
      >
        <Picker
          theme={theme}
          searchPlaceholder="Search..."
          lazyLoadEmojis
          allowExpandReactions={false}
          {...props}
          reactionsDefaultOpen
        />
      </PopoverContent>
    </Popover>
  )
}
