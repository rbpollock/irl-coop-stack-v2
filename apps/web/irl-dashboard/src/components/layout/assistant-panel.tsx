"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { Brain, Loader2, Plus, Send, Trash2, X } from "lucide-react"
import { useSession } from "next-auth/react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { getObject, listObjects, putObject, type StsCreds } from "@/lib/s3-browser"

const COOP_API_URL =
  process.env.NEXT_PUBLIC_COOP_API_URL ?? "https://api.irl.coop"
const DOCS_AREA_ID =
  process.env.NEXT_PUBLIC_RAG_DOCS_AREA_ID ?? "e418da84-6d62-4b31-aeff-fb2a5cff63d2"
const GROUPS_AREA_ID =
  process.env.NEXT_PUBLIC_RAG_GROUPS_AREA_ID ?? "ff498932-aae5-449a-a4db-13432cdf7e2b"

type MemoryFact = {
  id: string
  fact: string
  source: "member" | "assistant"
  kind: string
  created_at: string
}
type Context = {
  document_id?: string
  document_name?: string | null
  heading?: string | null
  text?: string
  source?: string
}
type Message = { role: "user" | "assistant"; text: string; sources?: Context[] }

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

// Retrieve contexts for one area, with the same 401 → anonymous fallback the
// docs search uses — a stale session token shouldn't blank the retrieval.
async function retrieve(
  token: string | undefined,
  areaId: string,
  question: string,
): Promise<Context[]> {
  const doFetch = async (withToken: boolean): Promise<Context[]> => {
    const res = await fetch(`${COOP_API_URL}/mcp`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(withToken && token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({
        jsonrpc: "2.0",
        id: 1,
        method: "tools/call",
        params: {
          name: "rag.retrieve_area_contexts",
          arguments: { area_id: areaId, question, rerank: false },
        },
      }),
    })
    if (res.status === 401 && withToken) return doFetch(false)
    if (!res.ok) return []
    const data = (await res.json()) as any
    if (data?.error) return []
    const text = data?.result?.content?.[0]?.text
    if (!text) return []
    try {
      return ((JSON.parse(text) as any).contexts ?? []) as Context[]
    } catch {
      return []
    }
  }
  return doFetch(Boolean(token))
}

// On-device generation via Chrome's built-in Prompt API. Throws when the model
// isn't available so the caller can degrade to retrieval-only.
async function generate(prompt: string): Promise<string> {
  const w = window as any
  if (!w.ai || typeof w.ai.createTextSession !== "function") {
    throw new Error("window.ai unavailable")
  }
  const session = await w.ai.createTextSession()
  return await session.prompt(prompt)
}

function buildPrompt(
  memory: MemoryFact[],
  contexts: Context[],
  question: string,
): string {
  const facts =
    memory.map((m) => `- ${m.fact}`).join("\n") || "(nothing remembered yet)"
  const ctx = contexts.length
    ? contexts
        .map(
          (c, i) =>
            `[${i + 1}] ${c.document_name ?? "doc"}${c.heading ? ` — ${c.heading}` : ""}: ${(c.text ?? "").slice(0, 600)}`,
        )
        .join("\n\n")
    : "(no relevant coop knowledge retrieved)"
  return [
    "You are the irl.coop assistant — a member-owned helper for a cooperative network.",
    "Answer ONLY from the member's memory and the retrieved coop knowledge below. Cite sources as [n].",
    "If neither is relevant, say you don't have it in the coop's knowledge.",
    "",
    `Member memory:\n${facts}`,
    "",
    `Relevant coop knowledge:\n${ctx}`,
    "",
    `Question: ${question}`,
  ].join("\n")
}

export function AssistantPanel() {
  const { data: session } = useSession()
  const token = session?.accessToken as string | undefined
  const [open, setOpen] = useState(false)
  const [tab, setTab] = useState<"chat" | "memory">("chat")

  // memory
  const [memories, setMemories] = useState<MemoryFact[]>([])
  const [memLoading, setMemLoading] = useState(false)
  const [draft, setDraft] = useState("")

  // chat
  const [messages, setMessages] = useState<Message[]>([])
  const [question, setQuestion] = useState("")
  const [thinking, setThinking] = useState(false)
  const [proposal, setProposal] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [noAi, setNoAi] = useState(false)
  const [creds, setCreds] = useState<StsCreds | null>(null)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)

  const loadMemories = useCallback(async () => {
    if (!token) return
    setMemLoading(true)
    try {
      const data = (await callTool(token, "memory.recall", {})) as {
        memories?: MemoryFact[]
      }
      setMemories(data.memories ?? [])
    } catch {
      setError("Could not load memory")
    } finally {
      setMemLoading(false)
    }
  }, [token])

  useEffect(() => {
    if (open) loadMemories()
  }, [open, loadMemories])

  // Detect the on-device model up front so the note shows before the first ask.
  useEffect(() => {
    if (open && typeof (window as any).ai?.createTextSession !== "function") {
      setNoAi(true)
    }
  }, [open])

  // Resume the last session: fetch scoped STS creds, LIST the member's prefix,
  // load the most recent transcript, and replay its messages.
  useEffect(() => {
    if (!open || !token) return
    ;(async () => {
      try {
        const res = await fetch(`${COOP_API_URL}/api/v1/chat/sts`, {
          headers: { Authorization: `Bearer ${token}` },
          cache: "no-store",
        })
        if (!res.ok) return
        const c = (await res.json()) as StsCreds
        setCreds(c)
        const objs = await listObjects(c, `${c.prefix}/`)
        const sessions = objs
          .filter((o) => o.key.endsWith(".json"))
          .sort((a, b) => b.lastModified.localeCompare(a.lastModified))
        if (sessions.length === 0) {
          setSessionId(crypto.randomUUID())
          setMessages([])
          return
        }
        const last = sessions[0]
        const id =
          last.key.split("/").pop()?.replace(/\.json$/, "") ?? crypto.randomUUID()
        setSessionId(id)
        const gres = await getObject(c, last.key)
        if (gres.ok) {
          const session = (await gres.json()) as { messages?: Message[] }
          setMessages(session.messages ?? [])
        }
      } catch {
        // transcript unavailable — chat still works, it just won't persist
      }
    })()
  }, [open, token])

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight })
  }, [messages, thinking])

  const remember = async (fact: string, source: "member" | "assistant") => {
    if (!fact.trim() || !token) return
    try {
      await callTool(token, "memory.remember", { fact: fact.trim(), source })
      setDraft("")
      await loadMemories()
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

  // Persist the current conversation to the member's chat prefix (read-modify-
  // write one session object). Non-fatal — the chat works without persistence.
  const saveTranscript = async (msgs: Message[]) => {
    if (!creds || !sessionId) return
    try {
      const body = JSON.stringify({
        version: 1,
        sessionId,
        updatedAt: new Date().toISOString(),
        messages: msgs,
      })
      await putObject(creds, `${creds.prefix}/${sessionId}.json`, body)
    } catch {
      // persist failure — non-fatal
    }
  }

  const newSession = () => {
    setSessionId(crypto.randomUUID())
    setMessages([])
    setProposal(null)
  }

  const ask = async () => {
    const q = question.trim()
    if (!q || !token || thinking) return
    setQuestion("")
    const base: Message[] = [...messages, { role: "user", text: q }]
    setMessages(base)
    setThinking(true)
    setError(null)
    setProposal(null)
    try {
      // 1. recall memory
      const mem = (await callTool(token, "memory.recall", {})) as {
        memories?: MemoryFact[]
      }
      // 2. retrieve context (docs + groups, the union)
      const [docs, groups] = await Promise.all([
        retrieve(token, DOCS_AREA_ID, q),
        retrieve(token, GROUPS_AREA_ID, q),
      ])
      const contexts = [...groups, ...docs]

      // 3+4. generate (on-device), degrading to retrieval-only
      let answer = ""
      let usedAi = false
      try {
        answer = await generate(buildPrompt(mem.memories ?? [], contexts, q))
        usedAi = true
      } catch {
        setNoAi(true)
      }
      const full: Message[] = [
        ...base,
        { role: "assistant", text: answer, sources: contexts },
      ]
      setMessages(full)
      saveTranscript(full)

      // 5. propose one durable fact, surfaced for the member to keep/discard
      if (usedAi) {
        try {
          const fact = await generate(
            [
              "From this exchange, extract ONE durable fact to remember about the member",
              '(a group they belong to, a need, a preference, or a decision).',
              'Reply with just the fact, or the single word "nothing".',
              "",
              `Member: ${q}`,
              answer ? `Assistant: ${answer.slice(0, 500)}` : "",
            ].join("\n"),
          )
          const clean = fact.trim().replace(/^["']|["']$/g, "")
          if (
            clean &&
            clean.toLowerCase() !== "nothing" &&
            !clean.toLowerCase().startsWith("nothing")
          ) {
            setProposal(clean)
          }
        } catch {
          /* no proposal */
        }
      }
    } catch {
      setError("Something went wrong")
      const full: Message[] = [
        ...base,
        { role: "assistant", text: "Something went wrong — please try again." },
      ]
      setMessages(full)
      saveTranscript(full)
    } finally {
      setThinking(false)
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
        <div className="fixed bottom-32 end-4 z-50 flex h-[70vh] w-[min(92vw,380px)] flex-col overflow-hidden rounded-xl border bg-background shadow-2xl">
          <div className="flex items-center justify-between border-b px-3 py-2">
            <span className="text-sm font-semibold">Assistant</span>
            <div className="flex items-center gap-1">
              {(["chat", "memory"] as const).map((t) => (
                <button
                  key={t}
                  onClick={() => setTab(t)}
                  className={`rounded px-2 py-0.5 text-xs capitalize ${
                    tab === t
                      ? "bg-primary/10 font-medium text-primary"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {t}
                </button>
              ))}
              <Button
                variant="ghost"
                size="icon"
                aria-label="Close"
                onClick={() => setOpen(false)}
              >
                <X className="size-4" />
              </Button>
            </div>
          </div>

          {tab === "chat" ? (
            <>
              <div
                ref={scrollRef}
                className="flex-1 space-y-3 overflow-y-auto p-3"
              >
                {messages.length === 0 && !thinking && (
                  <p className="py-6 text-center text-sm text-muted-foreground">
                    Ask the coop a question — I answer from what I remember about
                    you and the coop&apos;s knowledge.
                  </p>
                )}
                {messages.map((m, i) => (
                  <div
                    key={i}
                    className={`max-w-[88%] rounded-lg px-3 py-2 text-sm ${
                      m.role === "user"
                        ? "ms-auto bg-primary text-primary-foreground"
                        : "bg-muted"
                    }`}
                  >
                    <p className="whitespace-pre-wrap break-words">
                      {m.text ||
                        (m.sources && m.sources.length > 0
                          ? "Retrieved below — the on-device model isn't available."
                          : "Nothing relevant found in the coop's knowledge.")}
                    </p>
                    {m.sources && m.sources.length > 0 && (
                      <div className="mt-2 space-y-1 border-t pt-1.5 text-[10px] text-muted-foreground">
                        {m.sources.slice(0, 4).map((s, j) => (
                          <p key={j} className="truncate">
                            [{j + 1}] {s.document_name ?? "doc"}
                            {s.heading ? ` — ${s.heading}` : ""}
                          </p>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
                {thinking && (
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <Loader2 className="size-3.5 animate-spin" />
                    thinking…
                  </div>
                )}
                {noAi && (
                  <p className="text-center text-[11px] text-muted-foreground">
                    On-device model (Chrome Prompt API) isn&apos;t available —
                    showing retrieved sources only.
                  </p>
                )}
              </div>

              {proposal && (
                <div className="border-t px-3 py-2 text-xs">
                  <p className="mb-1.5 text-muted-foreground">
                    Remember this?
                  </p>
                  <p className="mb-2 rounded-md border p-2">{proposal}</p>
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      className="h-7 text-xs"
                      onClick={() => remember(proposal, "assistant")}
                    >
                      Keep
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-7 text-xs"
                      onClick={() => setProposal(null)}
                    >
                      Discard
                    </Button>
                  </div>
                </div>
              )}

              <div className="flex items-center gap-2 border-t p-2">
                <Button
                  size="icon"
                  variant="outline"
                  onClick={newSession}
                  aria-label="New session"
                  title="New session"
                >
                  <Plus className="size-4" />
                </Button>
                <Input
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && ask()}
                  placeholder="Ask the coop…"
                  className="h-9 text-sm"
                />
                <Button
                  size="icon"
                  onClick={ask}
                  aria-label="Ask"
                  disabled={thinking || !question.trim()}
                >
                  <Send className="size-4" />
                </Button>
              </div>
            </>
          ) : (
            <>
              <p className="border-b px-3 py-2 text-[11px] text-muted-foreground">
                Everything I remember about you — visible, and yours to erase.
              </p>
              <div className="flex-1 space-y-1.5 overflow-y-auto p-3">
                {memLoading && (
                  <div className="flex justify-center py-6">
                    <Loader2 className="size-5 animate-spin text-muted-foreground" />
                  </div>
                )}
                {!memLoading && memories.length === 0 && (
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
                        {m.source === "assistant"
                          ? " · proposed by assistant"
                          : ""}
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
                  onKeyDown={(e) => e.key === "Enter" && remember(draft, "member")}
                  placeholder="Add a fact to remember…"
                  className="h-9 text-sm"
                />
                <Button
                  size="icon"
                  onClick={() => remember(draft, "member")}
                  aria-label="Remember"
                >
                  <Plus className="size-4" />
                </Button>
              </div>
            </>
          )}

          {error && (
            <p className="px-3 pb-2 text-[11px] text-destructive">{error}</p>
          )}
        </div>
      )}
    </>
  )
}
