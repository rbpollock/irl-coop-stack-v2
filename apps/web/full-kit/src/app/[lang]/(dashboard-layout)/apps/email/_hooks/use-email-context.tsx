"use client"

import { useContext } from "react"

import { EmailContext } from "../_contexts/email-context"

export function useEmailContext() {
  const context = useContext(EmailContext)
  if (context === undefined) {
    throw new Error("useEmailContext must be used within a EmailProvider")
  }
  return context
}
