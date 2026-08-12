"use client"

import { useSearchParams } from "next/navigation"

import { ExternalLink } from "lucide-react"

import { Button } from "@/components/ui/button"

// Plane framed in the dashboard's content panel. The ?embed=1 flag tells
// plane's WorkspaceContentWrapper to hide its own top nav and app rail —
// the dashboard nav (Projects submenu) replaces them. In-app navigation
// keeps the chrome hidden via plane's sessionStorage.
const PLANE_URL = process.env.NEXT_PUBLIC_PLANE_URL ?? "https://plane.irl.coop"

export default function ProjectsPage() {
  const searchParams = useSearchParams()
  const planePath = searchParams.get("plane_path") ?? "/"
  const src = `${PLANE_URL}${planePath}${planePath.includes("?") ? "&" : "?"}embed=1`

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b bg-background px-4 py-2.5">
        <div>
          <h1 className="text-sm font-semibold">Projects</h1>
          <p className="text-xs text-muted-foreground">
            Plane — tasks, cycles and docs, framed from the coop
          </p>
        </div>
        <Button asChild variant="outline" size="sm">
          <a href={PLANE_URL} target="_blank" rel="noreferrer">
            <ExternalLink className="me-2 h-4 w-4" />
            Open full screen
          </a>
        </Button>
      </div>
      <iframe
        src={src}
        title="Projects"
        className="h-[calc(100svh-12rem)] w-full border-0"
        allow="fullscreen"
      />
    </div>
  )
}
