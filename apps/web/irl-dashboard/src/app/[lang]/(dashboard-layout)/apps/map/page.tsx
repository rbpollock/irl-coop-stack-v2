"use client"

import { ExternalLink } from "lucide-react"

import { Button } from "@/components/ui/button"

// Sovereign basemap framed in the dashboard's content panel. Public (no login):
// the page is served from maps.irl.coop (nginx), tiles pull from MinIO range
// requests — zero external mapping services.
const MAPS_URL = process.env.NEXT_PUBLIC_MAPS_URL ?? "https://maps.irl.coop"

export default function MapPage() {
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b bg-background px-4 py-2.5">
        <div>
          <h1 className="text-sm font-semibold">Maps</h1>
          <p className="text-xs text-muted-foreground">
            Sovereign basemap — self-hosted tiles and glyphs
          </p>
        </div>
        <Button asChild variant="outline" size="sm">
          <a href={MAPS_URL} target="_blank" rel="noreferrer">
            <ExternalLink className="me-2 h-4 w-4" />
            Open full screen
          </a>
        </Button>
      </div>
      <iframe
        src={MAPS_URL}
        title="Maps"
        className="h-[calc(100svh-12rem)] w-full border-0"
        allow="fullscreen"
      />
    </div>
  )
}
