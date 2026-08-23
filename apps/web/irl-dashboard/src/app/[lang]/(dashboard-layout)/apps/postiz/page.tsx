"use client"

import { ExternalLink } from "lucide-react"

import { Button } from "@/components/ui/button"

// Postiz framed in the dashboard's content panel. Postiz has no embed mode,
// so it renders its own chrome inside the frame. Zero-click SSO works in-frame
// because Postiz sends no frame-blocking headers and Keycloak's CSP is
// `frame-ancestors 'self' https://*.irl.coop` — so the unauthenticated bounce
// through Keycloak (and the login form, if needed) completes inside the frame.
const POSTIZ_URL =
  process.env.NEXT_PUBLIC_POSTIZ_URL ?? "https://postiz.irl.coop"

export default function PostizPage() {
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b bg-background px-4 py-2.5">
        <div>
          <h1 className="text-sm font-semibold">Social Media</h1>
          <p className="text-xs text-muted-foreground">
            Postiz — schedule and publish across social channels
          </p>
        </div>
        <Button asChild variant="outline" size="sm">
          <a href={POSTIZ_URL} target="_blank" rel="noreferrer">
            <ExternalLink className="me-2 h-4 w-4" />
            Open full screen
          </a>
        </Button>
      </div>
      <iframe
        src={POSTIZ_URL}
        title="Postiz"
        className="h-[calc(100svh-12rem)] w-full border-0 bg-white"
        allow="fullscreen"
      />
    </div>
  )
}
