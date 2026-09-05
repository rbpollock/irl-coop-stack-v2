import type { ReactNode } from "react"

// The chat route is now a full-page Element iframe — no narrow chat-panel
// wrapper. Render children full-width in the dashboard layout's content area.
export default function ChatLayout({ children }: { children: ReactNode }) {
  return <>{children}</>
}
