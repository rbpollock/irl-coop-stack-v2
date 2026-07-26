"use client"

import type { EmailType } from "../types"

import { CardContent } from "@/components/ui/card"

export function EmailViewContentBody({ email }: { email: EmailType }) {
  return (
    <CardContent className="whitespace-pre-wrap">{email.content}</CardContent>
  )
}
