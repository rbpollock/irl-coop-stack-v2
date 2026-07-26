import type { EmailType } from "../types"

import { useEmailContext } from "../_hooks/use-email-context"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Table, TableBody } from "@/components/ui/table"
import { EmailListContentRowDesktop } from "./email-list-row-desktop"

export function EmailListContentDesktop() {
  const { emailState } = useEmailContext()

  const selectedEmailsSet = new Set(
    emailState.selectedEmails.map((email) => email.id)
  )

  return (
    <ScrollArea className="h-[calc(100vh-16.5rem)]">
      <Table>
        <TableBody>
          {emailState.emails.map((email: EmailType) => {
            const isSelected = selectedEmailsSet.has(email.id)

            return (
              <EmailListContentRowDesktop
                key={email.id}
                email={email}
                isSelected={isSelected}
              />
            )
          })}
        </TableBody>
      </Table>
    </ScrollArea>
  )
}
