"use client"

import { useState } from "react"
import { MessagesSquare, X } from "lucide-react"

import type { DictionaryType } from "@/lib/get-dictionary"

import { Button } from "@/components/ui/button"

const ELEMENT_URL =
  process.env.NEXT_PUBLIC_ELEMENT_URL ?? "https://element.irl.coop"

// The coop chat: an iframe panel embedding Element Web. It rides the same
// SSO as every app — the homeserver session comes from the realm session
// (one consent the first time), so the widget is just a frame around the
// same chat the member already has.
export function ChatWidget({ dictionary }: { dictionary: DictionaryType }) {
  const [open, setOpen] = useState(false)

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
          <iframe
            src={ELEMENT_URL}
            title={dictionary.navigation.coopChat}
            className="h-full w-full flex-1 border-0 bg-background"
            allow="clipboard-read; clipboard-write; microphone; camera; display-capture"
          />
        </div>
      )}
    </>
  )
}
