import type { NavigationType } from "@/types"

export const sidebarNavigationData: NavigationType[] = [
  {
    title: "Overview",
    items: [
      {
        title: "Introduction",
        href: "/docs/overview/introduction",
        iconName: "Play",
      },
      {
        title: "Kits",
        href: "/docs/overview/kits",
        iconName: "Folders",
      },
      {
        title: "Installation",
        href: "/docs/overview/installation",
        iconName: "ArrowDownToLine",
      },
      {
        title: "Deployment",
        href: "/docs/overview/deployment",
        iconName: "ArrowUpToLine",
      },
    ],
  },
  {
    title: "Development",
    items: [
      {
        title: "Authentication",
        href: "/docs/development/authentication",
        iconName: "Lock",
      },
      {
        title: "Internationalization (I18n)",
        href: "/docs/development/i18n",
        iconName: "Languages",
      },
      {
        title: "Navigation",
        href: "/docs/development/navigation",
        iconName: "Menu",
      },

      {
        title: "Theme Color",
        href: "/docs/development/theme-color",
        iconName: "SwatchBook",
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
