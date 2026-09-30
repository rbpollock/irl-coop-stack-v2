"use client"

// The weave's "act" seam — funds a drawn connection as a REAL Safe move, through
// coop-api POST /api/safe/session/execute → SessionKeyModule (Safe-1.4.1 module
// on the group Safe). Mirrors the dues client's fetch pattern: the NextAuth
// session's access token rides as a Bearer header to NEXT_PUBLIC_COOP_API_URL.
//
// What this client honestly is: the gesture's ON-RAMP to the real engine. When
// coop-api's session module is configured (local dev hardhat), a call here is a
// real budgeted spend under the caller's session key. When it isn't configured,
// the endpoint answers 503 "safe session module not configured" — and the UI
// must say so plainly rather than fake success.

export const COOP_API_URL =
  process.env.NEXT_PUBLIC_COOP_API_URL ?? "https://api.irl.coop"

export type SessionSpendResult = {
  txHash?: string
  target: string
  value: string
  token: string
  amountIn: string
  message: string
}

async function api<T>(path: string, token: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${COOP_API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...(init?.headers ?? {}),
    },
  })
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { error?: string }
    const err = new Error(body?.error ?? `Request failed (${res.status})`)
    ;(err as Error & { status?: number }).status = res.status
    throw err
  }
  return res.json() as Promise<T>
}

/**
 * Draw one real connection: the caller's session key drives the group Safe to
 * `target` for `amount` (USDC-denominated by default). Throws on refusal
 * (budget exceeded, allow-list, session module not configured).
 */
export function commitSessionSpend(
  token: string,
  target: string,
  amountIn: string,
  opts?: { value?: string; data?: string; tokenAddr?: string },
): Promise<SessionSpendResult> {
  return api<SessionSpendResult>("/api/safe/session/execute", token, {
    method: "POST",
    body: JSON.stringify({
      target,
      value: opts?.value ?? "0",
      data: opts?.data ?? "0x",
      token: opts?.tokenAddr,
      amountIn,
    }),
  })
}