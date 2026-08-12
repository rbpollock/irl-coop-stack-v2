"use client"

import { useEffect, useState } from "react"

import type { NavigationNestedItem, NavigationType } from "@/types"

import { navigationsData } from "@/data/navigations"

type PlaneProject = { id: string; name: string; url: string }

// Module-level cache so every nav renderer shares one fetch per tab session.
let cachedProjects: NavigationNestedItem[] | null = null

export function useNavigationsData(): NavigationType[] {
  const [projects, setProjects] = useState<NavigationNestedItem[]>(cachedProjects ?? [])

  useEffect(() => {
    if (cachedProjects) return
    fetch("/api/plane/projects")
      .then((r) => (r.ok ? r.json() : null))
      .then((data: { projects?: PlaneProject[] } | null) => {
        const items = (data?.projects ?? []).map((p) => ({
          title: p.name,
          href: `/apps/projects?plane_path=${encodeURIComponent(p.url)}`,
        }))
        cachedProjects = items
        setProjects(items)
      })
      .catch(() => {
        /* nav falls back to the static item — plane stays reachable */
      })
  }, [])

  // The static "Projects" entry becomes a collapsible parent; the live
  // project list (from plane's API, per member) fills its children.
  return navigationsData.map((nav) => ({
    ...nav,
    items: nav.items.map((item) =>
      item.title === "Projects"
        ? {
            title: item.title,
            iconName: "FolderKanban",
            items: [{ title: "All projects", href: "/apps/projects" }, ...projects],
          }
        : item
    ),
  }))
}
