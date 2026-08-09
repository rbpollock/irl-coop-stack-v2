import type { Metadata } from "next"

import { Activity, FolderKanban, Server, Users, Wallet } from "lucide-react"

import {
  DashboardCardActionsDropdown,
  DashboardOverviewCard,
} from "@/components/dashboards/dashboard-card"

// Plane CE project management — same-org SSO via Keycloak (zero per-service credentials)
const PLANE_URL = process.env.NEXT_PUBLIC_PLANE_URL ?? "http://localhost:3002"

// Define metadata for the page
export const metadata: Metadata = {
  title: "IRL Co-op Dashboard",
}

// Mock data — replace with real API calls when the backend is wired up
const overviewData = {
  activeNodes: { value: 12, percentageChange: 8.3 },
  safeWallets: { value: 89, percentageChange: 14.7 },
  members: { value: 342, percentageChange: 5.2 },
  pendingTxns: { value: 23, percentageChange: -11.4 },
}

function OverviewCards() {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 md:col-span-full md:grid-cols-4">
      <DashboardOverviewCard
        data={overviewData.activeNodes}
        title="Active Shard Nodes"
        period="Last 30 days"
        icon={Server}
        action={<DashboardCardActionsDropdown />}
      />
      <DashboardOverviewCard
        data={overviewData.safeWallets}
        title="Safe Wallets"
        period="Total deployed"
        icon={Wallet}
        action={<DashboardCardActionsDropdown />}
      />
      <DashboardOverviewCard
        data={overviewData.members}
        title="Members"
        period="All time"
        icon={Users}
        action={<DashboardCardActionsDropdown />}
      />
      <DashboardOverviewCard
        data={overviewData.pendingTxns}
        title="Pending Transactions"
        period="Awaiting execution"
        icon={Activity}
        action={<DashboardCardActionsDropdown />}
      />
    </div>
  )
}

function NetworkStatusSection() {
  const shardNodes = [
    { id: 1, name: "Shard Node Alpha", status: "online", uptime: "99.8%", region: "US-East" },
    { id: 2, name: "Shard Node Beta", status: "online", uptime: "99.6%", region: "EU-West" },
    { id: 3, name: "Shard Node Gamma", status: "online", uptime: "99.9%", region: "APAC" },
    { id: 4, name: "Shard Node Delta", status: "syncing", uptime: "87.2%", region: "US-West" },
  ]

  return (
    <div className="col-span-full grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      <h3 className="col-span-full text-lg font-semibold">Network Status</h3>
      {shardNodes.map((node) => (
        <div
          key={node.id}
          className="flex flex-col gap-2 rounded-lg border bg-card p-4 shadow-sm"
        >
          <div className="flex items-center justify-between">
            <span className="font-medium text-sm">{node.name}</span>
            <span
              className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${
                node.status === "online"
                  ? "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400"
                  : "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400"
              }`}
            >
              <span
                className={`inline-block size-1.5 rounded-full ${
                  node.status === "online" ? "bg-green-500" : "bg-yellow-500"
                }`}
              />
              {node.status === "online" ? "Online" : "Syncing"}
            </span>
          </div>
          <div className="flex justify-between text-sm text-muted-foreground">
            <span>Uptime: {node.uptime}</span>
            <span>{node.region}</span>
          </div>
        </div>
      ))}
    </div>
  )
}

function QuickActions() {
  return (
    <div className="col-span-full grid gap-4 md:grid-cols-3">
      <h3 className="col-span-full text-lg font-semibold">Quick Actions</h3>
      {[
        { label: "Deploy New Safe", description: "Create a new ERC-4337 smart wallet for a member", icon: Wallet },
        { label: "Add Shard Node", description: "Onboard a new sovereign shard to the cooperative", icon: Server },
        { label: "View Activity Log", description: "Inspect recent transactions and governance actions", icon: Activity },
      ].map((action) => (
        <button
          key={action.label}
          type="button"
          className="flex items-start gap-3 rounded-lg border bg-card p-4 text-left shadow-sm transition-colors hover:bg-accent"
        >
          <action.icon className="mt-0.5 size-5 shrink-0 text-muted-foreground" />
          <div>
            <div className="font-medium text-sm">{action.label}</div>
            <div className="text-xs text-muted-foreground">{action.description}</div>
          </div>
        </button>
      ))}
    </div>
  )
}

function ProjectTools() {
  return (
    <div className="col-span-full grid gap-4 md:grid-cols-3">
      <h3 className="col-span-full text-lg font-semibold">Project Tools</h3>
      {[
        {
          label: "Projects",
          description: "Plan, track, and collaborate — signed in with your co-op identity",
          icon: FolderKanban,
          href: PLANE_URL,
        },
      ].map((tool) => (
        <a
          key={tool.label}
          href={tool.href}
          target="_blank"
          rel="noreferrer"
          className="flex items-start gap-3 rounded-lg border bg-card p-4 text-left shadow-sm transition-colors hover:bg-accent"
        >
          <tool.icon className="mt-0.5 size-5 shrink-0 text-muted-foreground" />
          <div>
            <div className="font-medium text-sm">{tool.label}</div>
            <div className="text-xs text-muted-foreground">{tool.description}</div>
          </div>
        </a>
      ))}
    </div>
  )
}

export default function IRLCoopDashboardPage() {
  return (
    <section className="container grid gap-4 p-4 md:grid-cols-2">
      <OverviewCards />
      <NetworkStatusSection />
      <QuickActions />
      <ProjectTools />
    </section>
  )
}
