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

type Room = { id: string; name: string }

// The coop chat: a room-scoped Cinny embed. The room list comes from coop-api
// (GET /api/v1/chat/rooms — it mints the member's Matrix token via the SSO
// bounce and proxies joined_rooms); selecting a room deep-links Cinny into that
// room instead of loading the whole shell.
export function ChatWidget({ dictionary }: { dictionary: DictionaryType }) {
  const { data: session } = useSession()
  const token = session?.accessToken as string | undefined
  const [open, setOpen] = useState(false)
  const [rooms, setRooms] = useState<Room[]>([])
  const [roomId, setRoomId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!open || !token) return
    setError(null)
    fetch(`${COOP_API_URL}/api/v1/chat/rooms`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error("rooms failed"))))
      .then((data: { rooms?: Room[] }) => {
        const list = data.rooms ?? []
        setRooms(list)
        setRoomId((cur) => cur ?? list[0]?.id ?? null)
      })
      .catch(() => setError("Could not load rooms"))
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

          {rooms.length > 0 && (
            <div className="flex flex-wrap gap-1 border-b px-2 py-1.5">
              {rooms.map((r) => (
                <button
                  key={r.id}
                  onClick={() => setRoomId(r.id)}
                  className={
                    "truncate rounded-full px-2.5 py-1 text-xs font-medium transition-colors " +
                    (r.id === roomId
                      ? "bg-primary text-primary-foreground"
                      : "bg-muted text-muted-foreground hover:bg-muted/80")
                  }
                >
                  {r.name}
                </button>
              ))}
            </div>
          )}

          {roomId ? (
            <iframe
              src={`${CINNY_URL}/#/room/${encodeURIComponent(roomId)}`}
              title={dictionary.navigation.coopChat}
              className="h-full w-full flex-1 border-0 bg-background"
              allow="clipboard-read; clipboard-write; microphone; camera; display-capture"
            />
          ) : (
            <div className="flex flex-1 items-center justify-center p-4 text-sm text-muted-foreground">
              {error ?? "No rooms yet"}
            </div>
          )}
        </div>
      )}
    </>
  )
}
