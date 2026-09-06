"use client"

import { useEffect, useState } from "react"
import { MessagesSquare, X } from "lucide-react"
import { useSession } from "next-auth/react"

import type { DictionaryType } from "@/lib/get-dictionary"

import { Button } from "@/components/ui/button"

const CINNY_URL =
  process.env.NEXT_PUBLIC_CINNY_URL ?? "https://cinny.irl.coop"
const COOP_API_URL =
  process.env.NEXT_PUBLIC_COOP_API_URL ?? "https://api.irl.coop"

// The coop chat: a Cinny embed that logs in with a server-minted Matrix login
// token. coop-api drives the Synapse SSO flow server-side (it is the OIDC
// issuer), so the member's browser never hits the SSO consent screen — the
// iframe just consumes ?loginToken= and lands in the client.
export function ChatWidget({ dictionary }: { dictionary: DictionaryType }) {
  const { data: session } = useSession()
  const token = session?.accessToken as string | undefined
  const [open, setOpen] = useState(false)
  const [loginToken, setLoginToken] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!open || !token) return
    setError(null)
    setLoginToken(null)
    fetch(`${COOP_API_URL}/api/v1/chat/login`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error("login failed"))))
      .then((data: { loginToken?: string }) => {
        setLoginToken(data.loginToken ?? null)
        if (!data.loginToken) setError("Could not start chat")
      })
      .catch(() => setError("Could not start chat"))
  }, [open, token])

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

          {loginToken ? (
            <iframe
              src={`${CINNY_URL}/?loginToken=${encodeURIComponent(loginToken)}`}
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
