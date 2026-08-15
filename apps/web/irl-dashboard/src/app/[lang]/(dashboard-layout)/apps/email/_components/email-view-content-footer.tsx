"use client"

import { Forward, Reply } from "lucide-react"

import { Button } from "@/components/ui/button"
import { CardFooter } from "@/components/ui/card"

export function EmailViewContentFooter() {
  return (
    <CardFooter className="p-3 pt-0 gap-1.5">
      <Button variant="outline">
        <Reply className="me-2 h-4 w-4" />
        <span>Reply</span>
      </Button>
      <Button variant="outline">
        <Forward className="me-2 h-4 w-4" />
        <span>Forward</span>
      </Button>
    </CardFooter>
  )
}
