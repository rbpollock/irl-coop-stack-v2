import type { NavigationType } from "@/types"

// Side navigation organized by member personas:
//   Coop           — the daily workspace every member reaches for
//   Administration — the coop's operators: nodes, people, money
//   Account        — personal settings
//   Build          — the developers connecting to the API
// External services (Plane, NocoDB, coop-api) sign in with the same
// identity — no per-service credentials.
export const navigationsData: NavigationType[] = [
  {
    title: "Coop",
    items: [
      {
        title: "Home",
        href: "/dashboards/overview",
        iconName: "LayoutDashboard",
      },
      {
        title: "Projects",
        href: "/apps/projects",
        iconName: "FolderKanban",
      },
      {
        title: "Groups",
        href: "/apps/groups",
        iconName: "Network",
      },
      {
        title: "Databases",
        href: process.env.NEXT_PUBLIC_NOCODB_URL ?? "https://nocodb.irl.coop",
        iconName: "Database",
      },
      {
        title: "Webmail",
        href: "/apps/webmail",
        iconName: "Mail",
      },
      {
        title: "Files",
        href: "/apps/files",
        iconName: "FolderOpen",
      },
      {
        title: "Documents",
        href: "/apps/docs",
        iconName: "FileText",
      },
    ],
  },
  {
    title: "Administration",
    items: [
      {
        title: "Shard Nodes",
        href: "/dashboards/analytics",
        iconName: "Server",
      },
      {
        title: "Members",
        href: "/dashboards/crm",
        iconName: "Users",
      },
      {
        title: "Safes",
        href: "/dashboards/ecommerce",
        iconName: "Wallet",
      },
    ],
  },
  {
    title: "Account",
    items: [
      {
        title: "Profile",
        href: "/pages/account/profile",
        iconName: "User",
      },
      {
        title: "Settings",
        href: "/pages/account/settings",
        iconName: "UserCog",
      },
    ],
  },
  {
    title: "Build",
    items: [
      {
        title: "API",
        href: process.env.NEXT_PUBLIC_COOP_API_URL ?? "https://api.irl.coop",
        iconName: "Braces",
      },
    ],
  },
]
