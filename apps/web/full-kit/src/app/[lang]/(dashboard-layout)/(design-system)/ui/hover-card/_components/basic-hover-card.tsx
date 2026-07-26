"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  HoverCard,
  HoverCardContent,
  HoverCardTrigger,
} from "@/components/ui/hover-card"

export function BasicHoverCard() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Basic Hover Card</CardTitle>
      </CardHeader>
      <CardContent className="flex justify-center items-center">
        <HoverCard>
          <HoverCardTrigger>Hover</HoverCardTrigger>
          <HoverCardContent>
            The React Framework – created and maintained by @vercel.
          </HoverCardContent>
        </HoverCard>
      </CardContent>
    </Card>
  )
}
