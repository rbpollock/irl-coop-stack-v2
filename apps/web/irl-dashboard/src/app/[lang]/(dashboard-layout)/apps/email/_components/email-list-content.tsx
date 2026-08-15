"use client"

import { useEffect } from "react"
import { useParams, useSearchParams } from "next/navigation"
import { useMedia } from "react-use"

import { useEmailContext } from "../_hooks/use-email-context"
import { CardContent } from "@/components/ui/card"
import { EmailListContentDesktop } from "./email-list-content-desktop"
import { EmailListContentHeader } from "./email-list-content-header"
import { EmailListContentMobile } from "./email-list-content-mobile"

export function EmailListContent() {
  const { handleGetFilteredEmails } = useEmailContext()
  const params = useParams()
  const searchParams = useSearchParams()
  const isMediumOrSmaller = useMedia("(max-width: 767px)")

  const page = searchParams.get("page")
    ? parseInt(searchParams.get("page") as string)
    : 1 // Get the current page from the search params, default to page 1
  const filter = params.filter as string

  useEffect(() => {
    handleGetFilteredEmails(filter, page)
  }, [page, filter, handleGetFilteredEmails])

  return (
    <CardContent className="flex-1 h-full flex flex-col p-0">
      <EmailListContentHeader />
      {isMediumOrSmaller ? (
        <EmailListContentMobile />
      ) : (
        <EmailListContentDesktop />
      )}
    </CardContent>
  )
}
