import type { ActiveProjectType } from "../types"

export const activeProjectsData: ActiveProjectType[] = [
  {
    name: "E-Commerce Platform Redesign",
    progress: 85,
    startDate: new Date("2024-01-15T00:00:00Z"),
    dueDate: new Date("2024-10-01T00:00:00Z"),
    status: "On Track",
  },
  {
    name: "Mobile App Development",
    progress: 60,
    startDate: new Date("2024-03-10T00:00:00Z"),
    dueDate: new Date("2024-09-30T00:00:00Z"),
    status: "At Risk",
  },
  {
    name: "Marketing Automation Setup",
    progress: 40,
    startDate: new Date("2024-05-05T00:00:00Z"),
    dueDate: new Date("2024-12-15T00:00:00Z"),
    status: "On Hold",
  },
  {
    name: "Cloud Migration",
    progress: 20,
    startDate: new Date("2024-06-01T00:00:00Z"),
    dueDate: new Date("2025-03-01T00:00:00Z"),
    status: "On Track",
  },
  {
    name: "Customer Support Portal Upgrade",
    progress: 90,
    startDate: new Date("2023-12-01T00:00:00Z"),
    dueDate: new Date("2024-08-15T00:00:00Z"),
    status: "On Track",
  },
]
