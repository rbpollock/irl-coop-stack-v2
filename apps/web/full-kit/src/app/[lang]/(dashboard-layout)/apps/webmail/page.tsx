import type { Metadata } from "next"

import { ExternalLink } from "lucide-react"

import { Button } from "@/components/ui/button"

// Roundcube webmail — SSO via Keycloak (same realm as the shadboard; the
// iframe relies on the browser's Keycloak session cookie for auto-login).
const WEBMAIL_URL = process.env.NEXT_PUBLIC_WEBMAIL_URL ?? "https://webmail.irl.coop"

export const metadata: Metadata = {
  title: "Webmail",
}

export default function WebmailPage() {
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b bg-background px-4 py-2.5">
        <div>
          <h1 className="text-sm font-semibold">Webmail</h1>
          <p className="text-xs text-muted-foreground">
            Roundcube on stalwart — one irl.coop identity, no separate login
          </p>
        </div>
        <Button asChild variant="outline" size="sm">
          <a href={WEBMAIL_URL} target="_blank" rel="noreferrer">
            <ExternalLink className="me-2 h-4 w-4" />
            Open full screen
          </a>
        </Button>
      </div>
      <iframe
        src={WEBMAIL_URL}
        title="Webmail"
        className="h-[calc(100svh-12rem)] w-full border-0 bg-white"
        allow="fullscreen"
      />
    </div>
  )
}
