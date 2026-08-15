"use client"

import { useMemo } from "react"
import { useParams } from "next/navigation"

import { useEmailContext } from "../_hooks/use-email-context"
import { Card } from "@/components/ui/card"
import { EmailNotFound } from "./email-not-found"
import { EmailViewContent } from "./email-view-content"
import { EmailViewHeader } from "./email-view-header"

export function EmailView() {
  const { emailState } = useEmailContext()
  const params = useParams()

  const emailIdParam = params.id // Get the email ID from route params

  const email = useMemo(() => {
    if (emailIdParam) {
      // Find the email by ID
      return emailState.initialEmails.find((email) => email.id === emailIdParam)
    }

    // Return null if not found
    return null
  }, [emailIdParam, emailState.initialEmails])

  // If no matching email is found, show a not found UI
  if (!email) return <EmailNotFound />

  return (
    <Card className="flex-1 w-full md:w-auto">
      <EmailViewHeader email={email} />
      <EmailViewContent email={email} />
    </Card>
  )
}
