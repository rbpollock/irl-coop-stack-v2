"use client"

import { useCallback, useEffect, useState } from "react"
import Link from "next/link"
import { useParams } from "next/navigation"
import { useSession } from "next-auth/react"
import {
  ArrowLeft,
  Boxes,
  Check,
  Copy,
  Megaphone,
  Pencil,
  Plus,
  RefreshCw,
  Shield,
  UserPlus,
} from "lucide-react"

import { ensureLocalizedPathname } from "@/lib/i18n"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
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
import { Textarea } from "@/components/ui/textarea"
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
  inviteMember,
  listGroups,
  listMembers,
  listResources,
  scopeResource,
  updateGroup,
  type Group,
  type GroupPrivacy,
  type Member,
  type MemberVisibility,
  type Resource,
} from "../_lib/groups"

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

const APP_CHOICES = ["plane", "nocodb", "docs", "files", "matrix", "chat", "projects"]

function shortAddress(a: string) {
  return a.length > 18 ? `${a.slice(0, 10)}…${a.slice(-6)}` : a
}

function shortSub(s: string) {
  return s.length > 24 ? `${s.slice(0, 20)}…` : s
}

function relativeDate(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  })
}

export default function GroupDetailPage() {
  const { data: session } = useSession()
  const params = useParams<{ id: string; lang: string }>()
  const id = params.id
  const locale = params.lang ?? "en"

  const [group, setGroup] = useState<Group | null>(null)
  const [members, setMembers] = useState<Member[]>([])
  const [resources, setResources] = useState<Resource[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  const [editOpen, setEditOpen] = useState(false)
  const [editName, setEditName] = useState("")
  const [editDescription, setEditDescription] = useState("")
  const [savingEdit, setSavingEdit] = useState(false)

  const [inviteOpen, setInviteOpen] = useState(false)
  const [inviteSub, setInviteSub] = useState("")
  const [inviteRoles, setInviteRoles] = useState("member")
  const [inviteAlias, setInviteAlias] = useState("")
  const [inviteVisibility, setInviteVisibility] =
    useState<MemberVisibility>("canonical")
  const [inviting, setInviting] = useState(false)

  const [scopeOpen, setScopeOpen] = useState(false)
  const [scopeApp, setScopeApp] = useState("")
  const [scopeKey, setScopeKey] = useState("")
  const [scoping, setScoping] = useState(false)
  const [connectingPostiz, setConnectingPostiz] = useState(false)

  const token = session?.accessToken as string | undefined
  const isOwner = !!group?.roles?.includes("owner")
  const postizConnected = resources.some((r) => r.app === "postiz")

  const load = useCallback(() => {
    if (!token) return
    setLoading(true)
    setError(null)
    Promise.all([
      listGroups(token),
      listMembers(token, id),
      listResources(token, id),
    ])
      .then(([gs, ms, rs]) => {
        const g = gs.find((x) => x.id === id) ?? null
        setGroup(g)
        setMembers(ms)
        setResources(rs)
        if (g) {
          setEditName(g.name)
          setEditDescription(g.description ?? "")
        }
      })
      .catch((err) => setError((err as Error).message))
      .finally(() => setLoading(false))
  }, [token, id])

  useEffect(() => {
    load()
  }, [load])

  function openEdit() {
    if (!group) return
    setEditName(group.name)
    setEditDescription(group.description ?? "")
    setEditOpen(true)
  }

  async function handleEdit() {
    if (!token) return
    setSavingEdit(true)
    setError(null)
    try {
      const updated = await updateGroup(token, id, {
        name: editName.trim(),
        description: editDescription.trim(),
      })
      setGroup(updated)
      setEditOpen(false)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setSavingEdit(false)
    }
  }

  async function handlePrivacy(next: GroupPrivacy) {
    if (!token || !group) return
    setError(null)
    try {
      const updated = await updateGroup(token, id, { privacy: next })
      setGroup(updated)
    } catch (err) {
      setError((err as Error).message)
    }
  }

  async function handleInvite() {
    if (!token || !inviteSub.trim()) return
    setInviting(true)
    setError(null)
    try {
      const roles = inviteRoles
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean)
      await inviteMember(token, id, {
        sub: inviteSub.trim(),
        roles: roles.length ? roles : ["member"],
        alias: inviteAlias.trim() || undefined,
        visibility: inviteVisibility,
      })
      setInviteSub("")
      setInviteRoles("member")
      setInviteAlias("")
      setInviteVisibility("canonical")
      setInviteOpen(false)
      load()
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setInviting(false)
    }
  }

  async function handleScope() {
    if (!token || !scopeApp || !scopeKey.trim()) return
    setScoping(true)
    setError(null)
    try {
      await scopeResource(token, id, {
        app: scopeApp,
        resource_key: scopeKey.trim(),
      })
      setScopeApp("")
      setScopeKey("")
      setScopeOpen(false)
      load()
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setScoping(false)
    }
  }

  function copyAddress() {
    if (!group?.safe_address) return
    navigator.clipboard.writeText(group.safe_address)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  // Connect Postiz to this group: scope app='postiz' with resource_key = the
  // group id (the deterministic Postiz Organization id). The postizSyncSweep
  // then provisions the org + seats within ~30s.
  async function handleConnectPostiz() {
    if (!token) return
    setConnectingPostiz(true)
    setError(null)
    try {
      await scopeResource(token, id, { app: "postiz", resource_key: id })
      load()
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setConnectingPostiz(false)
    }
  }

  if (!token) return null

  if (loading) {
    return (
      <div className="space-y-4 p-4">
        <Skeleton className="h-20 w-full" />
        <Skeleton className="h-48 w-full" />
        <Skeleton className="h-48 w-full" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex items-center gap-3 p-4">
        <div className="flex-1 rounded border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
          {error}
        </div>
        <Button variant="outline" size="sm" onClick={load}>
          <RefreshCw className="me-2 h-3.5 w-3.5" />
          Retry
        </Button>
      </div>
    )
  }

  if (!group) {
    return (
      <div className="p-4">
        <div className="rounded border bg-background p-6 text-center text-sm text-muted-foreground">
          Group not found.
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b bg-background px-4 py-2.5">
        <div className="flex items-center gap-2">
          <Button asChild variant="ghost" size="icon" className="h-7 w-7">
            <Link href={ensureLocalizedPathname("/apps/groups", locale)}>
              <ArrowLeft className="h-4 w-4" />
            </Link>
          </Button>
          <div>
            <h1 className="flex items-center gap-2 text-sm font-semibold">
              {group.name}
              <Badge className={PRIVACY_META[group.privacy].className}>
                {PRIVACY_META[group.privacy].label}
              </Badge>
            </h1>
            <p className="text-xs text-muted-foreground">
              {group.description || "No description"}
            </p>
          </div>
        </div>
        {isOwner && (
          <Button size="sm" variant="outline" onClick={openEdit}>
            <Pencil className="me-2 h-3.5 w-3.5" />
            Edit
          </Button>
        )}
      </div>

      <div className="flex-1 space-y-4 overflow-auto p-4">
        <div className="grid gap-4 md:grid-cols-3">
          <Card className="md:col-span-2">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-sm">
                <Shield className="h-4 w-4" />
                Sovereign account
              </CardTitle>
              <CardDescription>
                The Safe this group acts through.
              </CardDescription>
            </CardHeader>
            <CardContent className="flex items-center gap-2">
              <code className="flex-1 truncate rounded bg-muted px-2 py-1 font-mono text-xs">
                {group.safe_address ?? "—"}
              </code>
              <Button
                size="icon"
                variant="ghost"
                className="h-7 w-7"
                onClick={copyAddress}
              >
                {copied ? (
                  <Check className="h-3.5 w-3.5 text-emerald-500" />
                ) : (
                  <Copy className="h-3.5 w-3.5" />
                )}
              </Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Privacy</CardTitle>
              <CardDescription>
                Who can see this group and its resources.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {isOwner ? (
                <Select
                  value={group.privacy}
                  onValueChange={(v) => handlePrivacy(v as GroupPrivacy)}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="open">Open — public</SelectItem>
                    <SelectItem value="members">Members — private</SelectItem>
                    <SelectItem value="hidden">Hidden — unlisted</SelectItem>
                  </SelectContent>
                </Select>
              ) : (
                <Badge className={PRIVACY_META[group.privacy].className}>
                  {PRIVACY_META[group.privacy].label}
                </Badge>
              )}
            </CardContent>
          </Card>
        </div>

        <Card>
          <CardHeader className="flex-row items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2 text-sm">
                <UserPlus className="h-4 w-4" />
                Members
              </CardTitle>
              <CardDescription>
                Seats — each with roles, an alias, and a visibility level.
              </CardDescription>
            </div>
            {isOwner && (
              <Button size="sm" onClick={() => setInviteOpen(true)}>
                <Plus className="me-2 h-4 w-4" />
                Invite
              </Button>
            )}
          </CardHeader>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Alias</TableHead>
                  <TableHead>Roles</TableHead>
                  <TableHead>Visibility</TableHead>
                  <TableHead className="hidden md:table-cell">Subject</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {members.length === 0 ? (
                  <TableRow>
                    <TableCell
                      colSpan={4}
                      className="text-center text-sm text-muted-foreground"
                    >
                      No members yet.
                    </TableCell>
                  </TableRow>
                ) : (
                  members.map((m) => (
                    <TableRow key={m.sub}>
                      <TableCell className="font-medium">
                        {m.alias ?? "—"}
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-wrap gap-1">
                          {m.roles.map((r) => (
                            <Badge key={r} variant="secondary">
                              {r}
                            </Badge>
                          ))}
                        </div>
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        {m.visibility}
                      </TableCell>
                      <TableCell className="hidden font-mono text-xs text-muted-foreground md:table-cell">
                        {shortSub(m.sub)}
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-sm">
              <Megaphone className="h-4 w-4" />
              Group apps
            </CardTitle>
            <CardDescription>
              Connected services. Connect Postiz to give this group a social
              media workspace — its own org, synced to the membership.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            <div className="flex items-center justify-between rounded border p-3">
              <div className="flex items-center gap-3">
                <Megaphone className="h-4 w-4 text-muted-foreground" />
                <div>
                  <div className="text-sm font-medium">Social Media</div>
                  <div className="text-xs text-muted-foreground">
                    Schedule + analytics across social channels (Postiz)
                  </div>
                </div>
              </div>
              {postizConnected ? (
                <Badge className="bg-emerald-500/10 text-emerald-700 dark:text-emerald-400">
                  Connected
                </Badge>
              ) : isOwner ? (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={handleConnectPostiz}
                  disabled={connectingPostiz}
                >
                  {connectingPostiz ? "Connecting…" : "Connect"}
                </Button>
              ) : (
                <span className="text-xs text-muted-foreground">
                  Owner can connect
                </span>
              )}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex-row items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2 text-sm">
                <Boxes className="h-4 w-4" />
                Scoped resources
              </CardTitle>
              <CardDescription>
                Apps and items that belong to this group.
              </CardDescription>
            </div>
            <Button size="sm" onClick={() => setScopeOpen(true)}>
              <Plus className="me-2 h-4 w-4" />
              Scope resource
            </Button>
          </CardHeader>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>App</TableHead>
                  <TableHead>Resource key</TableHead>
                  <TableHead className="hidden md:table-cell">Scoped</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {resources.length === 0 ? (
                  <TableRow>
                    <TableCell
                      colSpan={3}
                      className="text-center text-sm text-muted-foreground"
                    >
                      No scoped resources yet.
                    </TableCell>
                  </TableRow>
                ) : (
                  resources.map((r) => (
                    <TableRow key={`${r.app}:${r.resource_key}`}>
                      <TableCell>
                        <Badge variant="outline">{r.app}</Badge>
                      </TableCell>
                      <TableCell className="font-mono text-xs">
                        {r.resource_key}
                      </TableCell>
                      <TableCell className="hidden text-xs text-muted-foreground md:table-cell">
                        {relativeDate(r.scoped_at)}
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </div>

      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>Edit group</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="edit-name">Name</Label>
              <Input
                id="edit-name"
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit-description">Description</Label>
              <Textarea
                id="edit-description"
                value={editDescription}
                onChange={(e) => setEditDescription(e.target.value)}
                rows={3}
              />
            </div>
            {error && <p className="text-xs text-destructive">{error}</p>}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleEdit} disabled={savingEdit || !editName.trim()}>
              {savingEdit ? "Saving…" : "Save"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={inviteOpen} onOpenChange={setInviteOpen}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>Invite a member</DialogTitle>
            <DialogDescription>
              Seat a member by their identity subject (Keycloak sub).
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="invite-sub">Subject (sub)</Label>
              <Input
                id="invite-sub"
                value={inviteSub}
                onChange={(e) => setInviteSub(e.target.value)}
                placeholder="keycloak subject id"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="invite-roles">Roles (comma-separated)</Label>
              <Input
                id="invite-roles"
                value={inviteRoles}
                onChange={(e) => setInviteRoles(e.target.value)}
                placeholder="member, facilitator"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="invite-alias">Alias</Label>
              <Input
                id="invite-alias"
                value={inviteAlias}
                onChange={(e) => setInviteAlias(e.target.value)}
                placeholder="How they appear in this group"
              />
            </div>
            <div className="space-y-2">
              <Label>Visibility</Label>
              <Select
                value={inviteVisibility}
                onValueChange={(v) => setInviteVisibility(v as MemberVisibility)}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="role-only">Role only</SelectItem>
                  <SelectItem value="alias">Alias</SelectItem>
                  <SelectItem value="canonical">Canonical name</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {error && <p className="text-xs text-destructive">{error}</p>}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setInviteOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleInvite} disabled={inviting || !inviteSub.trim()}>
              {inviting ? "Inviting…" : "Invite"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={scopeOpen} onOpenChange={setScopeOpen}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>Scope a resource</DialogTitle>
            <DialogDescription>
              Attach an app&apos;s item (project, base, room) to this group.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>App</Label>
              <Select value={scopeApp} onValueChange={setScopeApp}>
                <SelectTrigger>
                  <SelectValue placeholder="Select an app" />
                </SelectTrigger>
                <SelectContent>
                  {APP_CHOICES.map((a) => (
                    <SelectItem key={a} value={a}>
                      {a}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="scope-key">Resource key</Label>
              <Input
                id="scope-key"
                value={scopeKey}
                onChange={(e) => setScopeKey(e.target.value)}
                placeholder="plane project id, nocodb base id, room id…"
              />
            </div>
            {error && <p className="text-xs text-destructive">{error}</p>}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setScopeOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleScope}
              disabled={scoping || !scopeApp || !scopeKey.trim()}
            >
              {scoping ? "Scoping…" : "Scope"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
