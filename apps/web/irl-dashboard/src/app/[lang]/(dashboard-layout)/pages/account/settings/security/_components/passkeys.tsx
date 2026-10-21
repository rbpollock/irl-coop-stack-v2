"use client"

import { useState } from "react"
import { useSession } from "next-auth/react"
import { CheckCircle, KeyRound, RefreshCw } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { registerPasskey } from "@/lib/passkey"

const COOP_API_URL =
  process.env.NEXT_PUBLIC_COOP_API_URL ?? "https://api.irl.coop"

// The passkey is more than a way to sign in — it is the key that OWNS this
// member's account Safe (B-11). Setting one up runs the WebAuthn ceremony here,
// hands the public key to coop-api, and the Safe is created owned by it: the
// platform never holds the account. The old Keycloak-only linkage stays
// available below as a secondary mechanism.
export function Passkeys() {
  const { data: session } = useSession()
  const token = session?.accessToken as string | undefined
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [safeAddress, setSafeAddress] = useState<string | null>(null)

  const onRegister = async () => {
    setBusy(true)
    setError(null)
    try {
      const res = await registerPasskey(
        token,
        session?.user?.name ?? "member",
        session?.user?.email ?? "member@irl.coop",
      )
      setSafeAddress(res.safe_address)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <KeyRound className="h-4 w-4" />
          Passkeys
        </CardTitle>
        <CardDescription>
          Your passkey is the key to your account — it signs you in, and it owns
          your account on-chain. The platform can&apos;t move your money.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {safeAddress ? (
          <div className="rounded border border-emerald-300/30 bg-emerald-500/5 p-3 text-xs text-emerald-800">
            <p className="flex items-center gap-1 font-semibold">
              <CheckCircle className="h-3.5 w-3.5" />
              Passkey registered
            </p>
            <p className="mt-1">
              Your account is owned by this passkey. Address:
            </p>
            <p className="mt-1 font-mono break-all">{safeAddress}</p>
          </div>
        ) : (
          <>
            <p className="text-sm text-muted-foreground">
              Use your device to create a passkey. It becomes the owner of your
              account, so nobody else — including us — holds a key to it.
            </p>
            <div className="mt-4">
              <Button size="sm" onClick={onRegister} disabled={busy || !token}>
                {busy ? (
                  <>
                    <RefreshCw className="mr-2 h-3.5 w-3.5 animate-spin" />
                    Waiting for your device…
                  </>
                ) : (
                  "Create a passkey"
                )}
              </Button>
            </div>
            <p className="mt-3 text-xs text-muted-foreground">
              Trouble on this device?{" "}
              <a
                className="underline"
                href={`${COOP_API_URL}/api/v1/auth/passkey/link`}
              >
                Set one up through sign-in instead
              </a>
              .
            </p>
          </>
        )}

        {error && (
          <div className="mt-3 rounded border border-destructive/30 bg-destructive/5 p-3 text-xs text-destructive">
            {error}
          </div>
        )}
      </CardContent>
    </Card>
  )
}