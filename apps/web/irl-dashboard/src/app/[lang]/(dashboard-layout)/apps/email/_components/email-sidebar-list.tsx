"use client"

import { useParams } from "next/navigation"

import type { LocaleType } from "@/types"

import { useEmailContext } from "../_hooks/use-email-context"
import { EmailSidebarItem } from "./email-sidebar-item"

export function EmailSidebarList() {
  const { emailState } = useEmailContext()
  const params = useParams()

  const locale = params.lang as LocaleType
  const segmentParam = params.segment

  return (
    <ul className="p-3 pt-0">
      <nav className="space-y-1.5">
        {emailState.sidebarItems.folders.map((item) => (
          <EmailSidebarItem
            key={item.name}
            item={item}
            segmentParam={segmentParam}
            locale={locale}
          />
        ))}

        <div>
          <h4 className="mt-4 mb-1 ms-4">Labels</h4>
          {emailState.sidebarItems.labels.map((item) => (
            <EmailSidebarItem
              key={item.name}
              item={item}
              segmentParam={segmentParam}
              locale={locale}
            />
          ))}
        </div>
      </nav>
    </ul>
  )
}
