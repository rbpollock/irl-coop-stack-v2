"use client"

import { useState } from "react"
import Link from "next/link"
import {
  Activity,
  Bell,
  Calculator,
  CalendarDays,
  ClipboardList,
  Database,
  FileText,
  FolderKanban,
  FolderOpen,
  Gift,
  Handshake,
  Mail,
  Map,
  Megaphone,
  Network,
  Phone,
  Radio,
  Scale,
  Search,
  Sprout,
  TriangleAlert,
  Video,
  Waypoints,
  X,
} from "lucide-react"

import type { LucideIcon } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { DocsSearch } from "@/components/docs-search"

// The coop's home, as a phone/tablet home screen: apps on top, widgets on bottom.
// Apps can have a green dot indicator for notifications.
// Widgets can be minimized/dismissed into a right panel with badge counts.

type App = {
  title: string
  href: string
  icon: LucideIcon
  gradient: string
  external?: boolean
  hasNotification?: boolean
}

const APPS: App[] = [
  {
    title: "Projects",
    href: "/apps/projects",
    icon: FolderKanban,
    gradient: "from-indigo-500 to-blue-600",
    hasNotification: true,
  },
  {
    title: "Farm",
    href: "/apps/farm",
    icon: Sprout,
    gradient: "from-emerald-500 to-green-600",
  },
  {
    title: "Video & Chat",
    href: "/apps/chat",
    icon: Video,
    gradient: "from-violet-500 to-purple-600",
    hasNotification: true,
  },
  {
    title: "Maps",
    href: "/apps/map",
    icon: Map,
    gradient: "from-teal-500 to-cyan-600",
  },
  {
    title: "Webmail",
    href: "/apps/webmail",
    icon: Mail,
    gradient: "from-sky-500 to-blue-600",
    hasNotification: true,
  },
  {
    title: "Calls",
    href: "/apps/calls",
    icon: Phone,
    gradient: "from-rose-500 to-red-600",
  },
  {
    title: "Files",
    href: "/apps/files",
    icon: FolderOpen,
    gradient: "from-amber-500 to-orange-600",
  },
  {
    title: "Docs",
    href: "/design",
    icon: FileText,
    gradient: "from-zinc-500 to-slate-600",
  },
  {
    title: "Groups",
    href: "/apps/groups",
    icon: Network,
    gradient: "from-fuchsia-500 to-pink-600",
  },
  {
    title: "Needs & Offers",
    href: "/dashboards/needs-offers",
    icon: Handshake,
    gradient: "from-teal-500 to-emerald-600",
  },
  {
    title: "Dues",
    href: "/dashboards/dues",
    icon: Scale,
    gradient: "from-amber-500 to-orange-600",
  },
  {
    title: "Databases",
    href: "https://nocodb.irl.coop",
    icon: Database,
    gradient: "from-cyan-500 to-sky-600",
    external: true,
  },
  {
    title: "Surveys",
    href: "https://forms.irl.coop",
    icon: ClipboardList,
    gradient: "from-orange-500 to-amber-600",
    external: true,
  },
  {
    title: "Events",
    href: "https://events.irl.coop",
    icon: CalendarDays,
    gradient: "from-lime-500 to-emerald-600",
    external: true,
  },
  {
    title: "Accounting",
    href: "https://accounting.irl.coop",
    icon: Calculator,
    gradient: "from-yellow-500 to-amber-600",
    external: true,
  },
  {
    title: "Stream",
    href: "/apps/stream",
    icon: Radio,
    gradient: "from-red-500 to-rose-600",
  },
  {
    title: "Social",
    href: "/apps/social-media",
    icon: Megaphone,
    gradient: "from-pink-500 to-fuchsia-600",
  },
]

type WidgetConfig = {
  id: string
  title: string
  icon: LucideIcon
  gradient: string
  count?: number
  className?: string
  content: React.ReactNode
}

function AppTile({ app }: { app: App }) {
  const inner = (
    <div className="relative group flex flex-col items-center gap-2">
      <div
        className={`flex size-14 items-center justify-center rounded-2xl bg-gradient-to-br ${app.gradient} shadow-md shadow-black/10 ring-1 ring-black/10 transition-transform duration-150 group-hover:scale-110 group-active:scale-95 sm:size-16`}
      >
        <app.icon className="size-6 text-white sm:size-7" strokeWidth={1.75} />
      </div>
      {app.hasNotification && (
        <span className="absolute top-0 right-3 size-3.5 rounded-full bg-emerald-500 ring-2 ring-background shadow-sm" />
      )}
      <span className="text-center text-[11px] font-medium leading-tight text-foreground/80 sm:text-xs">
        {app.title}
      </span>
    </div>
  )

  if (app.external) {
    return (
      <a
        href={app.href}
        target="_blank"
        rel="noreferrer"
        className="flex flex-col items-center"
      >
        {inner}
      </a>
    )
  }
  return (
    <Link href={app.href} className="flex flex-col items-center">
      {inner}
    </Link>
  )
}

function Soon() {
  return (
    <Badge
      variant="outline"
      className="text-[10px] font-normal text-muted-foreground"
    >
      soon
    </Badge>
  )
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground/70">
      {children}
    </h2>
  )
}

export function PhoneHome() {
  const [minimizedWidgets, setMinimizedWidgets] = useState<string[]>([])

  const initialWidgets: WidgetConfig[] = [
    {
      id: "notifications",
      title: "Notifications",
      icon: Bell,
      gradient: "from-indigo-500 to-blue-600",
      count: 3,
      className: "col-span-2",
      content: (
        <div className="flex flex-col items-center justify-center py-4 text-center">
          <p className="text-sm font-medium text-foreground/85">
            3 new updates
          </p>
          <p className="mt-1 max-w-[24ch] text-xs leading-relaxed text-muted-foreground">
            Mentions, decisions and group activity land here.
          </p>
        </div>
      ),
    },
    {
      id: "regenerative-score",
      title: "Regenerative score",
      icon: Sprout,
      gradient: "from-emerald-500 to-green-600",
      content: (
        <div className="flex items-center gap-4">
          <div className="relative shrink-0">
            <svg className="size-16 -rotate-90" viewBox="0 0 36 36">
              <circle
                cx="18"
                cy="18"
                r="15"
                fill="none"
                stroke="var(--muted)"
                strokeWidth="3.5"
              />
            </svg>
            <div className="absolute inset-0 flex items-center justify-center">
              <span className="text-lg font-semibold text-muted-foreground">
                —
              </span>
            </div>
          </div>
          <div className="space-y-1.5">
            <p className="text-xs leading-relaxed text-muted-foreground">
              Private care given &amp; received.
            </p>
            <Soon />
          </div>
        </div>
      ),
    },
    {
      id: "group-health",
      title: "Group health",
      icon: Activity,
      gradient: "from-teal-500 to-cyan-600",
      content: (
        <div className="flex flex-col items-center justify-center py-4 text-center">
          <p className="text-sm font-medium text-foreground/85">
            No groups yet
          </p>
          <p className="mt-1 max-w-[24ch] text-xs leading-relaxed text-muted-foreground">
            Status per group: decisions, weaves, unread.
          </p>
          <div className="mt-2">
            <Soon />
          </div>
        </div>
      ),
    },
    {
      id: "governance",
      title: "Governance",
      icon: Scale,
      gradient: "from-fuchsia-500 to-pink-600",
      count: 1,
      content: (
        <div className="flex flex-col items-center justify-center py-4 text-center">
          <p className="text-sm font-medium text-foreground/85">1 open vote</p>
          <p className="mt-1 max-w-[24ch] text-xs leading-relaxed text-muted-foreground">
            Choices your groups are asking you to weigh in on.
          </p>
        </div>
      ),
    },
    {
      id: "weaves",
      title: "Weaves",
      icon: Waypoints,
      gradient: "from-violet-500 to-purple-600",
      content: (
        <div className="flex flex-col items-center justify-center py-4 text-center">
          <p className="text-sm font-medium text-foreground/85">
            No pending weaves
          </p>
          <p className="mt-1 max-w-[24ch] text-xs leading-relaxed text-muted-foreground">
            Needs and offers you&apos;re helping connect.
          </p>
          <div className="mt-2">
            <Soon />
          </div>
        </div>
      ),
    },
    {
      id: "needs",
      title: "Needs",
      icon: Search,
      gradient: "from-rose-500 to-red-600",
      content: (
        <div className="flex flex-col items-center justify-center py-4 text-center">
          <p className="text-sm font-medium text-foreground/85">
            No open needs
          </p>
          <p className="mt-1 max-w-[24ch] text-xs leading-relaxed text-muted-foreground">
            What your community is asking for.
          </p>
          <div className="mt-2">
            <Soon />
          </div>
        </div>
      ),
    },
    {
      id: "offers",
      title: "Offers",
      icon: Gift,
      gradient: "from-amber-500 to-orange-600",
      content: (
        <div className="flex flex-col items-center justify-center py-4 text-center">
          <p className="text-sm font-medium text-foreground/85">
            No offers yet
          </p>
          <p className="mt-1 max-w-[24ch] text-xs leading-relaxed text-muted-foreground">
            What you and your groups can give.
          </p>
          <div className="mt-2">
            <Soon />
          </div>
        </div>
      ),
    },
  ]

  const minimize = (id: string) => {
    if (!minimizedWidgets.includes(id)) {
      setMinimizedWidgets([...minimizedWidgets, id])
    }
  }

  const restore = (id: string) => {
    setMinimizedWidgets(minimizedWidgets.filter((w) => w !== id))
  }

  const activeWidgets = initialWidgets.filter(
    (w) => !minimizedWidgets.includes(w.id)
  )
  const hiddenWidgets = initialWidgets.filter((w) =>
    minimizedWidgets.includes(w.id)
  )

  return (
    <div className="flex gap-6 items-start relative">
      {/* Main content area */}
      <div className="flex-1 space-y-8 min-w-0">
        {/* Under-development notice */}
        <div className="flex items-start gap-3 rounded-2xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-amber-900 dark:text-amber-200">
          <TriangleAlert
            className="mt-0.5 size-4 shrink-0 text-amber-600 dark:text-amber-400"
            strokeWidth={2}
          />
          <p className="text-xs leading-relaxed">
            <span className="font-semibold">
              irl.coop is under active development.
            </span>{" "}
            Features are subject to change, the platform is still experimental,
            and data loss is likely. Please don&apos;t rely on it for anything
            you can&apos;t afford to lose.
          </p>
        </div>

        {/* Search — docs, public groups and rooms */}
        <section>
          <DocsSearch className="max-w-none" prioritizeGroups />
        </section>

        {/* Apps — the icon grid on top */}
        <section className="space-y-3">
          <SectionLabel>Apps</SectionLabel>
          <div className="grid grid-cols-4 gap-x-2 gap-y-6 sm:grid-cols-6 lg:grid-cols-8">
            {APPS.map((app) => (
              <AppTile key={app.title} app={app} />
            ))}
          </div>
        </section>

        {/* Widgets on bottom */}
        <section className="space-y-3">
          <SectionLabel>Widgets</SectionLabel>
          {activeWidgets.length === 0 ? (
            <div className="rounded-3xl border border-dashed p-8 text-center text-sm text-muted-foreground">
              All widgets minimized. Restore them from the right panel.
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
              {activeWidgets.map((widget) => {
                const Icon = widget.icon
                return (
                  <div
                    key={widget.id}
                    className={`rounded-3xl border bg-card p-4 shadow-sm relative group ${widget.className ?? ""}`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <div
                          className={`flex size-6 items-center justify-center rounded-lg bg-gradient-to-br ${widget.gradient}`}
                        >
                          <Icon
                            className="size-3.5 text-white"
                            strokeWidth={2}
                          />
                        </div>
                        <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                          {widget.title}
                        </span>
                      </div>
                      <button
                        onClick={() => minimize(widget.id)}
                        className="opacity-0 group-hover:opacity-100 transition-opacity size-6 rounded-full flex items-center justify-center text-muted-foreground hover:bg-muted hover:text-foreground"
                        title="Minimize widget"
                      >
                        <X className="size-3.5" />
                      </button>
                    </div>
                    <div className="mt-3">{widget.content}</div>
                  </div>
                )
              })}
            </div>
          )}
        </section>
      </div>

      {/* Right side minimized widget panel (shown when there are minimized widgets) */}
      {hiddenWidgets.length > 0 && (
        <aside className="w-16 shrink-0 flex flex-col items-center gap-3 py-4 bg-card/60 backdrop-blur border rounded-3xl shadow-sm sticky top-6">
          <span className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground [writing-mode:vertical-lr] rotate-180 mb-2">
            Minimized
          </span>
          {hiddenWidgets.map((widget) => {
            const Icon = widget.icon
            return (
              <button
                key={widget.id}
                onClick={() => restore(widget.id)}
                className="relative group p-2 rounded-2xl hover:bg-muted transition-colors"
                title={`Restore ${widget.title}`}
              >
                <div
                  className={`flex size-10 items-center justify-center rounded-xl bg-gradient-to-br ${widget.gradient} shadow-sm`}
                >
                  <Icon className="size-5 text-white" strokeWidth={1.75} />
                </div>
                {widget.count !== undefined && widget.count > 0 && (
                  <span className="absolute top-1 right-1 flex size-5 items-center justify-center rounded-full bg-emerald-500 text-[10px] font-bold text-white shadow-sm ring-2 ring-background">
                    {widget.count}
                  </span>
                )}
              </button>
            )
          })}
        </aside>
      )}
    </div>
  )
}
