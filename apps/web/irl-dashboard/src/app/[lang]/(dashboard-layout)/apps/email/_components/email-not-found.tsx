import { MailX } from "lucide-react"

import { Card, CardContent } from "@/components/ui/card"
import { EmailMenuButton } from "./email-menu-button"

export function EmailNotFound() {
  return (
    <Card className="flex-1 w-full md:w-auto">
      <CardContent className="size-full flex flex-col justify-center items-center gap-2 p-0">
        <MailX className="size-24 text-primary/50" />
        <p className="text-muted-foreground">
          No email found. Please select an existing email or compose a new
          email.
        </p>
        <EmailMenuButton />
      </CardContent>
    </Card>
  )
}
