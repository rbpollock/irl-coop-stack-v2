import type { ReactNode } from "react"

import { chatsData } from "./_data/chats"

import { ChatWrapper } from "./_components/chat-wrapper"

export default function ChatLayout({ children }: { children: ReactNode }) {
  return <ChatWrapper chatsData={chatsData}>{children}</ChatWrapper>
}
