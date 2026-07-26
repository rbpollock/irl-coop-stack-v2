"use client"

import { EllipsisVertical } from "lucide-react"

import type { CheckedState } from "@radix-ui/react-checkbox"

import { useEmailContext } from "../_hooks/use-email-context"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"

export function EmailListContentHeader() {
  const { emailState, handleToggleSelectAllEmails } = useEmailContext()

  const hasSelectedEmails = !emailState.selectedEmails.length
  let isCheckboxChecked: CheckedState

  // If the number of selected emails equals the total number of emails
  if (emailState.selectedEmails.length === emailState.emails.length) {
    isCheckboxChecked = true

    // If there are any selected emails but not all of them
  } else if (emailState.selectedEmails.length > 0) {
    isCheckboxChecked = "indeterminate"

    // No emails are selected
  } else {
    isCheckboxChecked = false
  }

  return (
    <div className="flex items-center justify-between p-1 ps-3 border-b border-border md:p-2 md:ps-4">
      <Checkbox
        checked={isCheckboxChecked}
        onCheckedChange={handleToggleSelectAllEmails}
        aria-label="Select all emails"
      />
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="ghost"
            size="icon"
            onClick={(e) => e.stopPropagation()}
            aria-label="Email actions"
            disabled={hasSelectedEmails}
          >
            <EllipsisVertical className="h-4 w-4" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem>Archive</DropdownMenuItem>
          <DropdownMenuItem>Mark as spam</DropdownMenuItem>
          <DropdownMenuItem>Delete</DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  )
}
