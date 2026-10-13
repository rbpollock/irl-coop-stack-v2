import { coopJson } from "@/lib/coop-api"

// Client for the coop-api telephony surface. Mirrors the groups/webmail inline
// fetch pattern: the NextAuth session access token rides as a Bearer header to
// NEXT_PUBLIC_COOP_API_URL.
export const COOP_API_URL =
  process.env.NEXT_PUBLIC_COOP_API_URL ?? "https://api.irl.coop"

export type SipConfig = {
  server: string
  domain: string
  extension: string
  profileUserID: string
  password: string
  fullname: string | null
  avatar: string | null
  wss: { port: string; path: string }
}

async function api<T>(
  path: string,
  token: string,
  init?: RequestInit
): Promise<T> {
  return coopJson<T>(path, token, init)
}

export function getSipConfig(token: string) {
  return api<SipConfig>("/api/v1/telephony/sip-config", token)
}
