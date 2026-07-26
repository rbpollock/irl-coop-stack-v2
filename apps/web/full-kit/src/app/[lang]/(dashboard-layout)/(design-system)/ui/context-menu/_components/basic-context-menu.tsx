"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  ContextMenu,
  ContextMenuContent,
  ContextMenuItem,
  ContextMenuTrigger,
} from "@/components/ui/context-menu"

export function BasicContextMenu() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Basic Context Menu</CardTitle>
      </CardHeader>
      <CardContent className="h-80">
        <ContextMenu>
          <ContextMenuTrigger className="size-full flex justify-center items-center">
            Right click
          </ContextMenuTrigger>
          <ContextMenuContent>
            <ContextMenuItem>Profile</ContextMenuItem>
            <ContextMenuItem>Billing</ContextMenuItem>
            <ContextMenuItem>Team</ContextMenuItem>
            <ContextMenuItem>Subscription</ContextMenuItem>
          </ContextMenuContent>
        </ContextMenu>
      </CardContent>
    </Card>
  )
}
