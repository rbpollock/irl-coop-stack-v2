"use client"

import { Calendar } from "lucide-react"

import type { ActiveProjectType } from "../types"

import { cn, formatDate } from "@/lib/utils"

import { ActiveProjectsItemChart } from "./active-projects-item-chart"

const statusColors = {
  "On Track": {
    text: "text-success",
    chart: "hsl(var(--success))",
  },
  "At Risk": {
    text: "text-destructive",
    chart: "hsl(var(--destructive))",
  },
  "On Hold": {
    text: "text-muted-foreground",
    chart: "hsl(var(--muted-foreground))",
  },
}

export function ActiveProjectsItem({
  project,
}: {
  project: ActiveProjectType
}) {
  const textColor = statusColors[project.status].text
  const chartColor = statusColors[project.status].chart

  return (
    <li className="flex items-center gap-4 py-2 px-4 bg-card border rounded-lg">
      <ActiveProjectsItemChart value={project.progress} color={chartColor} />
      <div>
        <p className={cn(textColor, "text-xs font-semibold")}>
          {project.status}
        </p>
        <h3 className="line-clamp-1">{project.name}</h3>
        <div className="flex items-center text-sm text-muted-foreground">
          <Calendar className="shrink-0 me-2 h-4 w-4" aria-hidden />
          <p className="text-sm">
            {formatDate(project.startDate)} - {formatDate(project.dueDate)}
          </p>
        </div>
      </div>
    </li>
  )
}
