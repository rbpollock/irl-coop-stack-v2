"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { EmailComposerForm } from "./email-composer-form"
import { EmailMenuButton } from "./email-menu-button"

export function EmailComposer() {
  return (
    <Card className="flex-1 w-full flex flex-col md:w-auto">
      <CardHeader className="flex-row items-center gap-x-1.5 space-y-0">
        <EmailMenuButton isIcon />
        <CardTitle>Compose Mail</CardTitle>
      </CardHeader>
      <CardContent className="flex-1 h-full p-0">
        <EmailComposerForm />
      </CardContent>
    </Card>
  )
}
