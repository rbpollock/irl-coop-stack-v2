import { KeyRound } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"

// The Keycloak account console's "Signing in" section — passkey management.
// The linking flow lives there: the console requires an authenticated
// Keycloak session, so a member without one re-authenticates via the
// secondary mechanism (Google) once — proving ownership — then the WebAuthn
// ceremony binds the passkey to the SAME account. Afterwards both the
// passkey and Google unlock it.
const COOP_API_URL =
  process.env.NEXT_PUBLIC_COOP_API_URL ?? "https://api.irl.coop"
const LINK_PASSKEY_URL = `${COOP_API_URL}/api/v1/auth/passkey/link`

export function Passkeys() {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <KeyRound className="h-4 w-4" />
          Passkeys
        </CardTitle>
        <CardDescription>
          Sign in without Google — a device-bound cryptographic key linked to
          this account.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-muted-foreground">
          Setting one up re-authenticates you once with Google to prove you own
          the account; afterwards both the passkey and Google unlock it.
        </p>
        <div className="mt-4">
          <Button asChild size="sm" variant="outline">
            <a href={LINK_PASSKEY_URL}>Set up a passkey</a>
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
