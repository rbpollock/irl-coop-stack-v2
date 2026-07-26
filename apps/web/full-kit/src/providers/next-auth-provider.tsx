"use client"

import { SessionProvider } from "next-auth/react"

import type { SessionProviderProps } from "next-auth/react"

export const NextAuthProvider = ({
  children,
  ...props
}: SessionProviderProps) => {
  return (
    <SessionProvider refetchOnWindowFocus={false} {...props}>
      {children}
    </SessionProvider>
  )
}
