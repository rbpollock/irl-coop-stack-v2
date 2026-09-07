"use client"

import { useCallback, useEffect, useState } from "react"
import { Brain, Loader2, Plus, Trash2, X } from "lucide-react"
import { useSession } from "next-auth/react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"

const COOP_API_URL =
  process.env.NEXT_PUBLIC_COOP_API_URL ?? "https://api.irl.coop"

type MemoryFact = {
  id: string
  fact: string
  source: "member" | "assistant"
  kind: string
  created_at: string
}

// Call a coop-api MCP tool and unwrap the JSON text content it returns.
async function callTool(
  token: string | undefined,
  name: string,
  args: Record<string, unknown> = {},
) {
  const res = await fetch(`${COOP_API_URL}/mcp`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({
      jsonrpc: "2.0",
      id: 1,
      method: "tools/call",
      params: { name, arguments: args },
    }),
  })
  const data = (await res.json()) as any
  if (data?.error) throw new Error(data.error.message)
  const text = data?.result?.content?.[0]?.text
  if (!text) return {}
  try {
    return JSON.parse(text)
  } catch {
    return {}
  }
}

// The assistant's explicit-memory surface: the member sees everything the
// harness remembers, adds facts directly, and erases any of them. The
// retrieve→generate chat loop hangs off this once the local model lands.
export function AssistantPanel() {
  const { data: session } = useSession()
  const token = session?.accessToken as string | undefined
  const [open, setOpen] = useState(false)
  const [memories, setMemories] = useState<MemoryFact[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [draft, setDraft] = useState("")

  const load = useCallback(async () => {
    if (!token) return
    setLoading(true)
    setError(null)
    try {
      const data = (await callTool(token, "memory.recall", {})) as {
        memories?: MemoryFact[]
      }
      setMemories(data.memories ?? [])
    } catch {
      setError("Could not load memory")
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => {
    if (open) load()
  }, [open, load])

  const remember = async () => {
    const fact = draft.trim()
    if (!fact || !token) return
    try {
      await callTool(token, "memory.remember", { fact })
      setDraft("")
      await load()
    } catch {
      setError("Could not save")
    }
  }

  const forget = async (id: string) => {
    if (!token) return
    try {
      await callTool(token, "memory.forget", { id })
      setMemories((prev) => prev.filter((m) => m.id !== id))
    } catch {
      setError("Could not erase")
    }
  }

  return (
    <>
      <Button
        variant="outline"
        size="icon"
        aria-label="Assistant"
        onClick={() => setOpen((v) => !v)}
        className="fixed bottom-20 end-4 z-50 size-12 rounded-full shadow-lg"
      >
        {open ? <X className="size-5" /> : <Brain className="size-5" />}
      </Button>
      {open && (
        <div className="fixed bottom-32 end-4 z-50 flex h-[60vh] w-[min(92vw,360px)] flex-col overflow-hidden rounded-xl border bg-background shadow-2xl">
          <div className="flex items-center justify-between border-b px-3 py-2">
            <span className="text-sm font-semibold">Assistant memory</span>
            <Button
              variant="ghost"
              size="icon"
              aria-label="Close"
              onClick={() => setOpen(false)}
            >
              <X className="size-4" />
            </Button>
          </div>

          <p className="border-b px-3 py-2 text-[11px] text-muted-foreground">
            Everything I remember about you — visible, and yours to erase.
          </p>

          <div className="flex-1 space-y-1.5 overflow-y-auto p-3">
            {loading && (
              <div className="flex justify-center py-6">
                <Loader2 className="size-5 animate-spin text-muted-foreground" />
              </div>
            )}
            {!loading && memories.length === 0 && (
              <p className="py-6 text-center text-sm text-muted-foreground">
                Nothing remembered yet.
              </p>
            )}
            {memories.map((m) => (
              <div
                key={m.id}
                className="flex items-start justify-between gap-2 rounded-md border p-2 text-xs"
              >
                <div className="min-w-0">
                  <p className="break-words">{m.fact}</p>
                  <p className="mt-0.5 text-[10px] text-muted-foreground">
                    {m.kind}
                    {m.source === "assistant" ? " · proposed by assistant" : ""}
                  </p>
                </div>
                <button
                  aria-label="Forget"
                  onClick={() => forget(m.id)}
                  className="shrink-0 rounded p-1 text-muted-foreground transition hover:bg-destructive/10 hover:text-destructive"
                >
                  <Trash2 className="size-3.5" />
                </button>
              </div>
            ))}
          </div>

          <div className="flex items-center gap-2 border-t p-2">
            <Input
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && remember()}
              placeholder="Add a fact to remember…"
              className="h-9 text-sm"
            />
            <Button size="icon" onClick={remember} aria-label="Remember">
              <Plus className="size-4" />
            </Button>
          </div>
          {error && (
            <p className="px-3 pb-2 text-[11px] text-destructive">{error}</p>
          )}
        </div>
      )}
    </>
  )
}
