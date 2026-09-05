import type { Metadata } from "next"

import { ChatIframe } from "../_components/chat-iframe"

// The coop's video & chat: Matrix/Element iframed from the sidenav (dark).
export const metadata: Metadata = {
  title: "Video & Chat",
}

export default function ChatPage() {
  return <ChatIframe />
}
