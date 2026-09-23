"use client"

import { useEffect, useState } from "react"
import { useSession } from "next-auth/react"
import { MessagesSquare, X } from "lucide-react"

import type { DictionaryType } from "@/lib/get-dictionary"

import { Button } from "@/components/ui/button"

const CINNY_URL = process.env.NEXT_PUBLIC_CINNY_URL ?? "https://cinny.irl.coop"
const COOP_API_URL =
  process.env.NEXT_PUBLIC_COOP_API_URL ?? "https://api.irl.coop"
const AUTHED_KEY = "irlcoop-chat-authed"

// The coop chat: a Cinny embed. On first open we mint a Matrix login token
// server-side (coop-api is the OIDC issuer) and hand it to Cinny via
// ?loginToken= so the browser never sees the SSO consent screen; Cinny then
// holds its session in its own IndexedDB. Subsequent opens skip the mint and
// just load Cinny, which restores that session.
export function ChatWidget({ dictionary }: { dictionary: DictionaryType }) {
  const { data: session } = useSession()
  const token = session?.accessToken as string | undefined
  const [open, setOpen] = useState(false)
  const [loginToken, setLoginToken] = useState<string | null>(null)
  const [authed, setAuthed] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!open || !token) return
    // Already handed Cinny a token once — let the iframe restore its session.
    if (localStorage.getItem(AUTHED_KEY)) {
      setAuthed(true)
      setLoginToken(null)
      return
    }
    setAuthed(false)
    setError(null)
    setLoginToken(null)
    fetch(`${COOP_API_URL}/api/v1/chat/login`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    })
      .then((r) =>
        r.ok ? r.json() : Promise.reject(new Error("login failed"))
      )
      .then((data: { loginToken?: string }) => {
        if (data.loginToken) {
          setLoginToken(data.loginToken)
          localStorage.setItem(AUTHED_KEY, "1")
        } else {
          setError("Could not start chat")
        }
      })
      .catch(() => setError("Could not start chat"))
  }, [open, token])

  const src = loginToken
    ? `${CINNY_URL}/?loginToken=${encodeURIComponent(loginToken)}`
    : authed
      ? CINNY_URL
      : null

  return (
    <>
      <Button
        variant="outline"
        size="icon"
        aria-label={dictionary.navigation.chat}
        onClick={() => setOpen((v) => !v)}
        className="fixed bottom-4 end-4 z-50 size-12 rounded-full shadow-lg"
      >
        {open ? (
          <X className="size-5" />
        ) : (
          <MessagesSquare className="size-5" />
        )}
      </Button>
      {open && (
        <div className="fixed bottom-20 end-4 z-50 flex h-[70vh] w-[min(92vw,380px)] flex-col overflow-hidden rounded-xl border bg-background shadow-2xl">
          <div className="flex items-center justify-between border-b px-3 py-2">
            <span className="text-sm font-semibold">
              {dictionary.navigation.coopChat}
            </span>
            <Button
              variant="ghost"
              size="icon"
              aria-label={dictionary.navigation.chatClose}
              onClick={() => setOpen(false)}
            >
              <X className="size-4" />
            </Button>
          </div>

          {src ? (
            <iframe
              src={src}
              title={dictionary.navigation.coopChat}
              className="h-full w-full flex-1 border-0 bg-background"
              allow="clipboard-read; clipboard-write; microphone; camera; display-capture"
            />
          ) : (
            <div className="flex flex-1 items-center justify-center p-4 text-sm text-muted-foreground">
              {error ?? "Loading…"}
            </div>
          )}
        </div>
      )}
    </>
  )
}
