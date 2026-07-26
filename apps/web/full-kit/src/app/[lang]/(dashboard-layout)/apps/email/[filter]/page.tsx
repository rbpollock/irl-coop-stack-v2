import type { EmailSidebarItemType } from "../types"

import { sidebarItemsData } from "../_data/emails-sidebar-items"

import { EmailList } from "../_components/email-list"
import { EmailNotFound } from "../_components/email-not-found"

export default async function EmailPage(props: {
  params: Promise<{ filter: string }>
}) {
  const params = await props.params
  const filter = params.filter

  // Check if the current segment corresponds to one of the defined sidebar items
  const isSidebarItem = Object.entries(sidebarItemsData).some(([_, items]) => {
    return items.some((item: EmailSidebarItemType) => item.name === filter)
  })

  // If the segment matches a sidebar item, display emails filtered by that item
  if (isSidebarItem) {
    return <EmailList />
  }

  return <EmailNotFound />
}
