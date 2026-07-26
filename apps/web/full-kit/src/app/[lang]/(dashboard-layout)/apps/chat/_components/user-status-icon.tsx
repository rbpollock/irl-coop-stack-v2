"use client"

import { memo } from "react"
import { Circle, CircleMinus, Moon } from "lucide-react"

export const UserStatusIcon = memo(
  ({ status, size }: { status: string; size: number | string }) => {
    switch (status) {
      case "ONLINE":
        return (
          <Circle
            className="text-success fill-success"
            size={size}
            aria-label={status}
          />
        )
      case "IDLE":
        return (
          <Moon
            className="text-yellow-400 fill-yellow-400"
            size={size}
            aria-label={status}
          />
        )
      case "DO_NOT_DISTURB":
        return (
          <CircleMinus
            className="text-destructive fill-destructive-foreground"
            size={size}
            aria-label={status.replace("_", " ")}
          />
        )
      default:
        return (
          <Circle
            className="text-muted-foreground"
            size={size}
            aria-label="OFFLINE"
          />
        )
    }
  }
)
UserStatusIcon.displayName = "UserStatusIcon"
