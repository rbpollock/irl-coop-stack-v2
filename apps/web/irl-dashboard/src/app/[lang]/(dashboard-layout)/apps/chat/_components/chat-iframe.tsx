"use client"

const CINNY_URL = process.env.NEXT_PUBLIC_CINNY_URL ?? "https://cinny.irl.coop"

// The coop's video/chat: the Cinny Matrix client (lighter + mobile-responsive,
// with video calling) iframed from the sidenav. Auth rides the homeserver's
// OIDC SSO; the call UI is Cinny's bundled Element Call widget.
export function ChatIframe() {
  return (
    <div className="flex h-[calc(100svh-6.82rem)] flex-col overflow-hidden">
      <iframe
        src={CINNY_URL}
        title="Video & chat"
        className="h-full w-full flex-1 border-0 bg-background"
        allow="clipboard-read; clipboard-write; microphone; camera; display-capture"
      />
    </div>
  )
}
