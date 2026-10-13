"use client"

import { SessionProvider } from "next-auth/react"

import type { SessionProviderProps } from "next-auth/react"

// The coop JWT in the session is short-lived (1h) and is refreshed SERVER-SIDE
// whenever the NextAuth session is read (configs/next-auth.ts). With no re-read
// the token silently expires and every API call 401s with "invalid_token" until
// the page is reloaded. Poll the session (and re-read when the tab regains
// focus) so the token stays fresh and every useSession() consumer sees it.
// Keep this well inside the server's 10-minute refresh window.
const SESSION_REFETCH_SECONDS = 5 * 60

export const NextAuthProvider = ({
  children,
  ...props
}: SessionProviderProps) => {
  return (
    <SessionProvider
      refetchInterval={SESSION_REFETCH_SECONDS}
      refetchOnWindowFocus
      {...props}
    >
      {children}
    </SessionProvider>
  )
}
