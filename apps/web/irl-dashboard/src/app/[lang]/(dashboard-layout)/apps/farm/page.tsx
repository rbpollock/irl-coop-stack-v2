"use client"

import { ExternalLink } from "lucide-react"

import { Button } from "@/components/ui/button"

// LiteFarm framed in the dashboard's content panel. The app is served behind
// the coop fleet gate (farm.irl.coop) — zero-click SSO once the webapp
// auto-login lands, so the iframe loads the member's farm directly.
const FARM_URL = process.env.NEXT_PUBLIC_FARM_URL ?? "https://farm.irl.coop"

export default function FarmPage() {
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b bg-background px-4 py-2.5">
        <div>
          <h1 className="text-sm font-semibold">Farm</h1>
          <p className="text-xs text-muted-foreground">
            LiteFarm — fields, crops, tasks and sales, scoped to your group
          </p>
        </div>
        <Button asChild variant="outline" size="sm">
          <a href={FARM_URL} target="_blank" rel="noreferrer">
            <ExternalLink className="me-2 h-4 w-4" />
            Open full screen
          </a>
        </Button>
      </div>
      <iframe
        src={FARM_URL}
        title="Farm"
        className="h-[calc(100svh-12rem)] w-full border-0"
        allow="fullscreen"
      />
    </div>
  )
}
