import {
  Database,
  FolderKanban,
  Mail,
  Server,
  Users,
  Wallet,
} from "lucide-react"

import type { Metadata } from "next"

import { CoopGreeting } from "@/components/dashboards/coop-greeting"
import StackHealth from "@/components/dashboards/stack-health"

export const metadata: Metadata = {
  title: "IRL Co-op Dashboard",
}

// External services sign in with the same coop identity (zero per-service credentials).
const NOCODB_URL =
  process.env.NEXT_PUBLIC_NOCODB_URL ?? "https://nocodb.irl.coop"

// Every important subject, one hop away.
const QUICK_LINKS = [
  {
    title: "Projects",
    description: "Plan and run cooperative projects",
    icon: FolderKanban,
    href: "/apps/projects",
  },
  {
    title: "Databases",
    description: "Shared tables and records for your group",
    icon: Database,
    href: NOCODB_URL,
    external: true,
  },
  {
    title: "Webmail",
    description: "Your @irl.coop mailbox",
    icon: Mail,
    href: "/apps/webmail",
  },
  {
    title: "Safes",
    description: "The coop's smart wallets",
    icon: Wallet,
    href: "/dashboards/ecommerce",
  },
  {
    title: "Members",
    description: "The people in your coop",
    icon: Users,
    href: "/dashboards/crm",
  },
  {
    title: "Shard Nodes",
    description: "The network's health at a glance",
    icon: Server,
    href: "/dashboards/analytics",
  },
]

function QuickAccess() {
  return (
    <div className="col-span-full grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
      <h3 className="col-span-full text-lg font-semibold">Quick access</h3>
      {QUICK_LINKS.map((link) => (
        <a
          key={link.title}
          href={link.href}
          {...(link.external ? { target: "_blank", rel: "noreferrer" } : {})}
          className="flex items-start gap-3 rounded-lg border bg-card p-4 shadow-sm transition-colors hover:border-primary/50 hover:bg-accent"
        >
          <link.icon className="mt-0.5 size-5 shrink-0 text-primary" />
          <div>
            <div className="font-medium text-sm">{link.title}</div>
            <div className="text-xs text-muted-foreground">
              {link.description}
            </div>
          </div>
        </a>
      ))}
    </div>
  )
}

export default function IRLCoopDashboardPage() {
  return (
    <section className="container grid gap-4 p-4 md:grid-cols-2">
      <CoopGreeting />
      <QuickAccess />
      <StackHealth />
    </section>
  )
}
