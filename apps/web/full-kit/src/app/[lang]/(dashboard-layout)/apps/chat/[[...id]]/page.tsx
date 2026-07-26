import { userData } from "@/data/user"

import { ChatBox } from "../_components/chat-box"
import { ChatBoxPlaceholder } from "../_components/chat-box-placeholder"

export default async function ChatBoxPage(props: {
  params: Promise<{ id: string[] }>
}) {
  const params = await props.params
  const chatIdParam = params.id?.[0]

  // If no chat is selected, show a placeholder UI
  if (!chatIdParam) return <ChatBoxPlaceholder />

  // Otherwize show a chat box
  return <ChatBox user={userData} />
}
