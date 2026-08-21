"use client"

import { useCallback, useEffect, useState } from "react"
import Link from "next/link"
import { useParams } from "next/navigation"
import { useSession } from "next-auth/react"
import { ChevronRight, Plus, RefreshCw, Users } from "lucide-react"

import { ensureLocalizedPathname } from "@/lib/i18n"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Skeleton } from "@/components/ui/skeleton"

import {
  createGroup,
  listGroups,
  type Group,
  type GroupPrivacy,
} from "./_lib/groups"

const PRIVACY_META: Record<GroupPrivacy, { label: string; className: string }> = {
  open: {
    label: "Open",
    className: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400",
  },
  members: {
    label: "Members",
    className: "bg-sky-500/10 text-sky-700 dark:text-sky-400",
  },
  hidden: { label: "Hidden", className: "bg-muted text-muted-foreground" },
}

function shortAddress(a: string | null | undefined) {
  if (!a) return "—"
  return a.length > 18 ? `${a.slice(0, 10)}…${a.slice(-6)}` : a
}

function relativeDate(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  })
}

export default function GroupsPage() {
  const { data: session } = useSession()
  const params = useParams()
  const locale = (params.lang as string) ?? "en"

  const [groups, setGroups] = useState<Group[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [dialogOpen, setDialogOpen] = useState(false)
  const [name, setName] = useState("")
  const [privacy, setPrivacy] = useState<GroupPrivacy>("members")
  const [creating, setCreating] = useState(false)

  const token = session?.accessToken as string | undefined

  const load = useCallback(() => {
    if (!token) return
    setLoading(true)
    setError(null)
    listGroups(token)
      .then(setGroups)
      .catch((err) => setError((err as Error).message))
      .finally(() => setLoading(false))
  }, [token])

  useEffect(() => {
    load()
  }, [load])

  async function handleCreate() {
    if (!token || !name.trim()) return
    setCreating(true)
    setError(null)
    try {
      await createGroup(token, { name: name.trim(), privacy })
      setName("")
      setPrivacy("members")
      setDialogOpen(false)
      load()
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setCreating(false)
    }
  }

  if (!token) return null

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b bg-background px-4 py-2.5">
        <div>
          <h1 className="text-sm font-semibold">Groups</h1>
          <p className="text-xs text-muted-foreground">
            A group is a Safe — members, roles, and scoped apps on one sovereign
            account
          </p>
        </div>
        <Button size="sm" onClick={() => setDialogOpen(true)}>
          <Plus className="me-2 h-4 w-4" />
          New group
        </Button>
      </div>

      <div className="flex-1 overflow-auto p-4">
        {loading ? (
          <div className="space-y-2">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-14 w-full" />
            ))}
          </div>
        ) : error ? (
          <div className="flex items-center gap-3 rounded border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
            <span>{error}</span>
            <Button variant="outline" size="sm" onClick={load}>
              <RefreshCw className="me-2 h-3.5 w-3.5" />
              Retry
            </Button>
          </div>
        ) : groups.length === 0 ? (
          <div className="flex flex-col items-center justify-center gap-3 py-16 text-center">
            <Users className="h-8 w-8 text-muted-foreground" />
            <p className="text-sm text-muted-foreground">No groups yet.</p>
            <Button size="sm" onClick={() => setDialogOpen(true)}>
              <Plus className="me-2 h-4 w-4" />
              Create your first group
            </Button>
          </div>
        ) : (
          <Card>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Group</TableHead>
                    <TableHead>My role</TableHead>
                    <TableHead>Privacy</TableHead>
                    <TableHead className="hidden md:table-cell">
                      Safe account
                    </TableHead>
                    <TableHead className="hidden md:table-cell">Created</TableHead>
                    <TableHead />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {groups.map((g) => (
                    <TableRow key={g.id} className="group/row">
                      <TableCell>
                        <Link
                          href={ensureLocalizedPathname(
                            `/apps/groups/${g.id}`,
                            locale
                          )}
                          className="block"
                        >
                          <div className="font-medium group-hover/row:underline">
                            {g.name}
                          </div>
                          {g.kind === "personal" && (
                            <span className="text-xs text-muted-foreground">
                              Personal group
                            </span>
                          )}
                        </Link>
                      </TableCell>
                      <TableCell>
                        <Badge variant="secondary">
                          {g.roles?.[0] ?? "member"}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Badge className={PRIVACY_META[g.privacy].className}>
                          {PRIVACY_META[g.privacy].label}
                        </Badge>
                      </TableCell>
                      <TableCell className="hidden md:table-cell">
                        <span className="font-mono text-xs text-muted-foreground">
                          {shortAddress(g.safe_address)}
                        </span>
                      </TableCell>
                      <TableCell className="hidden text-xs text-muted-foreground md:table-cell">
                        {relativeDate(g.created_at)}
                      </TableCell>
                      <TableCell className="text-right">
                        <ChevronRight className="ms-auto h-4 w-4 text-muted-foreground" />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        )}
      </div>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>New group</DialogTitle>
            <DialogDescription>
              Deploys a new Safe and seats you as owner.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="group-name">Name</Label>
              <Input
                id="group-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Cold Storage Co-op"
                autoFocus
              />
            </div>
            <div className="space-y-2">
              <Label>Privacy</Label>
              <Select
                value={privacy}
                onValueChange={(v) => setPrivacy(v as GroupPrivacy)}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="open">Open — anyone can find it</SelectItem>
                  <SelectItem value="members">
                    Members — members see everything
                  </SelectItem>
                  <SelectItem value="hidden">Hidden — private</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {error && <p className="text-xs text-destructive">{error}</p>}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleCreate} disabled={creating || !name.trim()}>
              {creating ? "Deploying…" : "Create group"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
