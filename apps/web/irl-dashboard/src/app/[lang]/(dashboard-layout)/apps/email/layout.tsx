import type { Metadata } from "next"
import type { ReactNode } from "react"

import { emailsData } from "./_data/emails"
import { sidebarItemsData } from "./_data/emails-sidebar-items"

import { EmailWrapper } from "./_components/email-wrapper"

// Define metadata for the page
// More info: https://nextjs.org/docs/app/building-your-application/optimizing/metadata
export const metadata: Metadata = {
  title: "Email",
}

export default function EmailLayout({ children }: { children: ReactNode }) {
  return (
    <EmailWrapper emailsData={emailsData} sidebarItemsData={sidebarItemsData}>
      {children}
    </EmailWrapper>
  )
}
