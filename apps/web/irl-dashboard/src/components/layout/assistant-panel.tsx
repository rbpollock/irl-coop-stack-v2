"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { useSession } from "next-auth/react"
import { Brain, Loader2, Plus, Send, Trash2, X } from "lucide-react"

import type { StsCreds } from "@/lib/s3-browser"

import { getObject, listObjects, putObject } from "@/lib/s3-browser"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"

const COOP_API_URL =
  process.env.NEXT_PUBLIC_COOP_API_URL ?? "https://api.irl.coop"
const DOCS_AREA_ID =
  process.env.NEXT_PUBLIC_RAG_DOCS_AREA_ID ??
  "e418da84-6d62-4b31-aeff-fb2a5cff63d2"
const GROUPS_AREA_ID =
  process.env.NEXT_PUBLIC_RAG_GROUPS_AREA_ID ??
  "ff498932-aae5-449a-a4db-13432cdf7e2b"

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
type GroupSeat = { slug: string; name: string; roles?: string[] }

// Call a coop-api MCP tool and unwrap the JSON text content it returns.
async function callTool(
  token: string | undefined,
  name: string,
  args: Record<string, unknown> = {}
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

// Retrieve contexts for one area, falling back to the anonymous (public-tier)
// principal whenever the token-based attempt fails or returns nothing — a stale
// or rag-rejected token must not blank the retrieval.
async function retrieve(
  token: string | undefined,
  areaId: string,
  question: string
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
    if (data?.error) {
      // upstream (rag) rejected the token or errored — fall back to public
      return withToken ? doFetch(false) : []
    }
    const text = data?.result?.content?.[0]?.text
    if (!text) return []
    try {
      const contexts = ((JSON.parse(text) as any).contexts ?? []) as Context[]
      // token-based retrieval returned nothing → fall back to the public tier
      if (withToken && contexts.length === 0) return doFetch(false)
      return contexts
    } catch {
      return []
    }
  }
  return doFetch(Boolean(token))
}

// The member's coop group SEATS — authoritative, read under their own JWT and so
// RLS-scoped to them. Injected as grounding so "which groups am I in" is
// answerable, instead of falling through to "not in the coop's knowledge".
async function loadMyGroups(token: string | undefined): Promise<GroupSeat[]> {
  if (!token) return []
  try {
    const data = (await callTool(token, "list_my_groups", {})) as {
      groups?: GroupSeat[]
    }
    return data.groups ?? []
  } catch {
    return []
  }
}

// Shared system prompt for both tiers.
const SYSTEM_PROMPT =
  "You are the irl.coop assistant — a member-owned helper for a cooperative network. " +
  "Answer ONLY from the member's memory, the member's coop groups, and the retrieved coop knowledge given below. " +
  "The member's group list is authoritative: answer questions about which groups they belong to from it directly. " +
  "Cite coop knowledge ONLY when you actually used a numbered [n] item; never write a bare [n] and never invent a citation. " +
  "If the answer is in none of those, say you don't have it in the coop's knowledge."

// Preferred tier: on-device generation via Chrome's built-in Prompt API. The
// current global is `LanguageModel` (the old window.ai.createTextSession() is
// deprecated). The prompt never leaves the browser. Throws when unavailable.
async function generateOnDevice(
  system: string,
  prompt: string,
  onDelta: (text: string) => void
): Promise<string> {
  if (!("LanguageModel" in globalThis)) {
    throw new Error("LanguageModel unavailable")
  }
  const session = await (globalThis as any).LanguageModel.create({
    initialPrompts: [{ role: "system", content: system }],
  })
  // promptStreaming() yields the answer as it is produced. Chrome has shipped
  // both a growing-cumulative and a delta shape for this, so normalise: if a
  // chunk extends what we already have it is cumulative, else append.
  let acc = ""
  for await (const chunk of session.promptStreaming(prompt)) {
    const piece = String(chunk ?? "")
    acc = piece.startsWith(acc) ? piece : acc + piece
    onDelta(acc)
  }
  return acc
}

// Fallback tier: the coop's shared CPU model (llm-inference), reached through
// coop-api, which holds the provider key — the browser never sees it. This is
// the provider seam: the harness asks for a completion and the platform tier
// answers, exactly as a member's own key would later.
async function generateServer(
  token: string | undefined,
  system: string,
  prompt: string,
  onDelta: (text: string) => void
): Promise<string> {
  const res = await fetch(`${COOP_API_URL}/api/v1/assistant/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({
      stream: true,
      messages: [
        { role: "system", content: system },
        { role: "user", content: prompt },
      ],
    }),
  })
  if (!res.ok || !res.body) throw new Error(`shared model failed (${res.status})`)

  // Read the SSE stream ({delta} … {done}) and expose the growing text.
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buf = ""
  let acc = ""
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buf += decoder.decode(value, { stream: true })
    const lines = buf.split("\n")
    buf = lines.pop() ?? ""
    for (const line of lines) {
      const trimmed = line.trim()
      if (!trimmed.startsWith("data:")) continue
      const payload = trimmed.slice(5).trim()
      if (!payload) continue
      let evt: any
      try {
        evt = JSON.parse(payload)
      } catch {
        continue
      }
      if (evt.delta) {
        acc += String(evt.delta)
        onDelta(acc)
      } else if (evt.error) {
        throw new Error(String(evt.error))
      }
    }
  }
  if (!acc) throw new Error("shared model returned nothing")
  return acc
}

// On-device first (nothing leaves the browser); the coop's shared model as the
// fallback when the Prompt API is absent (Firefox, Safari, older Chrome, a
// low-power device) or a local session fails. Throws only if BOTH fail.
async function generate(
  token: string | undefined,
  system: string,
  prompt: string,
  onDelta: (text: string) => void
): Promise<{ text: string; engine: "device" | "coop" }> {
  if ("LanguageModel" in globalThis) {
    try {
      return {
        text: await generateOnDevice(system, prompt, onDelta),
        engine: "device",
      }
    } catch {
      // local session failed — fall through to the coop tier
    }
  }
  return {
    text: await generateServer(token, system, prompt, onDelta),
    engine: "coop",
  }
}

function buildPrompt(
  memory: MemoryFact[],
  seats: GroupSeat[],
  contexts: Context[],
  question: string
): string {
  const facts =
    memory.map((m) => `- ${m.fact}`).join("\n") || "(nothing remembered yet)"
  const groups = seats.length
    ? seats
        .map(
          (g) =>
            `- ${g.name} (${g.slug})${g.roles?.length ? ` — roles: ${g.roles.join(", ")}` : ""}`
        )
        .join("\n")
    : "(the member holds no coop group seats)"
  const ctx = contexts.length
    ? contexts
        .map(
          (c, i) =>
            `[${i + 1}] ${c.document_name ?? "doc"}${c.heading ? ` — ${c.heading}` : ""}: ${(c.text ?? "").slice(0, 600)}`
        )
        .join("\n\n")
    : "(no relevant coop knowledge retrieved)"
  return [
    `Member memory:\n${facts}`,
    "",
    `Member's coop groups (authoritative):\n${groups}`,
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
  const [engine, setEngine] = useState<"device" | "coop" | null>(null)
  const [creds, setCreds] = useState<StsCreds | null>(null)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)
  // While generating, the spinner stands in for the bubble only until the first
  // token lands; after that the streaming text is its own progress indicator.
  const lastMsg = messages[messages.length - 1]
  const awaitingFirstToken =
    thinking && (!lastMsg || lastMsg.role !== "assistant" || !lastMsg.text)

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
    if (open && !("LanguageModel" in globalThis)) {
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
          last.key
            .split("/")
            .pop()
            ?.replace(/\.json$/, "") ?? crypto.randomUUID()
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
    setEngine(null)
    setNoAi(false)
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
      // 1. recall memory (degrade to empty on a stale token / recall failure —
      //    the retrieval + generation should still run on the public tier)
      let mem: { memories?: MemoryFact[] } = { memories: [] }
      try {
        mem = (await callTool(token, "memory.recall", {})) as {
          memories?: MemoryFact[]
        }
      } catch {
        // keep going without memory
      }
      // 2. retrieve coop knowledge (docs + groups, the union) AND the member's
      //    own seats — the latter from the live directory, so membership
      //    questions are answered from the roster, not from retrieval.
      const [docs, groupDocs, seats] = await Promise.all([
        retrieve(token, DOCS_AREA_ID, q),
        retrieve(token, GROUPS_AREA_ID, q),
        loadMyGroups(token),
      ])
      const contexts = [...groupDocs, ...docs]

      // 3+4. generate — on-device first, the coop's shared model as fallback,
      // degrading to retrieval-only only if neither answers.
      // Create the assistant bubble up front and fill it as tokens arrive — at
      // CPU speed a buffered answer is ~25s of dead air on a long reply.
      let answer = ""
      const onDelta = (text: string) => {
        answer = text
        setMessages([...base, { role: "assistant", text, sources: contexts }])
      }
      setMessages([...base, { role: "assistant", text: "", sources: contexts }])
      let usedAi = false
      try {
        const out = await generate(
          token,
          SYSTEM_PROMPT,
          buildPrompt(mem.memories ?? [], seats, contexts, q),
          onDelta
        )
        answer = out.text
        setEngine(out.engine)
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
          const fact = (
            await generate(
              token,
              SYSTEM_PROMPT,
              [
                "From this exchange, extract ONE durable fact to remember about the member",
                "(a group they belong to, a need, a preference, or a decision).",
                'Reply with just the fact, or the single word "nothing".',
                "",
                `Member: ${q}`,
                answer ? `Assistant: ${answer.slice(0, 500)}` : "",
              ].join("\n"),
              // the proposal renders in its own box once ready — it must not
              // stream into the answer bubble
              () => {}
            )
          ).text
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
                    Ask the coop a question — I answer from what I remember
                    about you and the coop&apos;s knowledge.
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
                        (thinking
                          ? ""
                          : m.sources && m.sources.length > 0
                            ? "Retrieved below — no model could answer."
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
                {awaitingFirstToken && (
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <Loader2 className="size-3.5 animate-spin" />
                    thinking…
                  </div>
                )}
                {noAi && (
                  <p className="text-center text-[11px] text-muted-foreground">
                    No assistant model could answer — showing retrieved sources
                    only.
                  </p>
                )}
                {!noAi && engine && (
                  <p className="text-center text-[11px] text-muted-foreground">
                    {engine === "device"
                      ? "Answered on your device — nothing left your browser."
                      : "Answered by the coop's shared model."}
                  </p>
                )}
              </div>

              {proposal && (
                <div className="border-t px-3 py-2 text-xs">
                  <p className="mb-1.5 text-muted-foreground">Remember this?</p>
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
                  onKeyDown={(e) =>
                    e.key === "Enter" && remember(draft, "member")
                  }
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
