import type { ReactNode } from "react"
import type { EmailSidebarItemsType, EmailType } from "../types"

import { EmailProvider } from "../_contexts/email-context"
import { EmailSidebar } from "./email-sidebar"

export function EmailWrapper({
  emailsData,
  sidebarItemsData,
  children,
}: {
  emailsData: EmailType[]
  sidebarItemsData: EmailSidebarItemsType
  children: ReactNode
}) {
  return (
    <EmailProvider emailsData={emailsData} sidebarItemsData={sidebarItemsData}>
      <section className="container h-full w-full flex gap-4 p-4">
        <EmailSidebar />
        {children}
      </section>
    </EmailProvider>
  )
}
