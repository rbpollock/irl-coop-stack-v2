"use client"

import { useEmailContext } from "../_hooks/use-email-context"
import { CardFooter } from "@/components/ui/card"

export function EmailListFooter() {
  const { emailState } = useEmailContext()

  const emailCount = emailState.emails.length // Count of emails currently displayed.
  const totalEmails = emailState.totalEmails.toLocaleString()

  return (
    <CardFooter className="justify-center py-3 border-t border-border">
      <p className="text-muted-foreground" role="status" aria-live="polite">
        {/* Display email count or a message when no emails are available. */}
        {emailCount
          ? `1-${emailCount} of ${totalEmails}`
          : "No emails available"}
      </p>
    </CardFooter>
  )
}
