import type { NavigationType } from "@/types"

export const sidebarNavigationData: NavigationType[] = [
  {
    title: "Overview",
    items: [
      {
        title: "irl.coop — Overview",
        href: "/docs/design/irl-coop-overview",
        iconName: "Play",
      },
      {
        title: "Identity Sovereignty & FedID",
        href: "/docs/design/identity-sovereignty-and-fedid",
        iconName: "Fingerprint",
      },
      {
        title: "Privacy-First Graphs & Finance",
        href: "/docs/design/privacy-first-graphs-and-finance",
        iconName: "Shield",
      },
      {
        title: "The Weave",
        href: "/docs/design/the-weave",
        iconName: "GitMerge",
      },
      {
        title: "Platform Cooperative",
        href: "/docs/design/platform-cooperative",
        iconName: "Landmark",
      },
      {
        title: "DevOps & Maintenance",
        href: "/docs/design/devops-and-maintenance",
        iconName: "Wrench",
      },
    ],
  },
  {
    title: "Design Docs",
    items: [
      {
        title: "Overview",
        href: "/docs/design",
        iconName: "BookOpen",
      },
      {
        title: "Pathways Integration",
        href: "/docs/design/pathways-integration",
        iconName: "GitBranch",
      },
      {
        title: "Weaving",
        href: "/docs/design/weavers",
        iconName: "GitMerge",
      },
      {
        title: "Group Model",
        href: "/docs/design/irl-coop-group",
        iconName: "Users",
      },
      {
        title: "Needs / Offers",
        href: "/docs/design/needs-offers-matching",
        iconName: "HeartHandshake",
      },
    ],
  },
  {
    title: "Miscellaneous",
    items: [
      {
        title: "Sources & Credits",
        href: "/docs/miscellaneous/sources-and-credits",
        iconName: "LibraryBig",
      },
    ],
  },
]
