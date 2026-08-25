"use client"

import { useEffect, useState } from "react"
import { useSession } from "next-auth/react"
import { Phone, RefreshCw, Radio, Settings2 } from "lucide-react"

import { Button } from "@/components/ui/button"
import { MemberAvatar } from "@/components/member-avatar"
import { Skeleton } from "@/components/ui/skeleton"
import { useHasGrant } from "@/hooks/use-has-grant"

import { getSipConfig, type SipConfig } from "./_lib/telephony"

// Platform admins (telephony.platform.admin) get a jump to the FusionPBX
// admin console. The grant is the same claim the pbx oauth2-proxy gate checks,
// so the link and the actual access stay in lockstep.
const PBX_ADMIN_URL = "https://pbx.irl.coop"

// The browserphone lives at /phone/index.html (vendored Browser-Phone). It is
// same-origin, so config is handed to it via sessionStorage — the SIP secret
// never rides a URL or a log. On mount we fetch the member's SIP config from
// coop-api and drop it into that slot before mounting the iframe.
const CONFIG_SLOT = "irlcoop.phone.config"

export default function CallsPage() {
  const { data: session } = useSession()
  const token = session?.accessToken as string | undefined
  const isPlatformAdmin = useHasGrant("telephony.platform.admin")

  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading")
  const [error, setError] = useState<string | null>(null)
  const [config, setConfig] = useState<SipConfig | null>(null)

  const load = () => {
    if (!token) return
    setStatus("loading")
    setError(null)
    getSipConfig(token)
      .then((cfg) => {
        try {
          sessionStorage.setItem(CONFIG_SLOT, JSON.stringify(cfg))
        } catch {
          /* storage unavailable — the iframe falls back to query params */
        }
        setConfig(cfg)
        setStatus("ready")
      })
      .catch((err) => {
        setError((err as Error).message)
        setStatus("error")
      })
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  if (!token) return null

  return (
    <div className="flex h-[calc(100svh-9.85rem)] flex-col">
      <div className="flex items-center justify-between border-b bg-background px-4 py-2.5">
        <div>
          <h1 className="text-sm font-semibold">Calls</h1>
          <p className="text-xs text-muted-foreground">
            Your in-app phone — a WebRTC softphone over{" "}
            <code className="font-mono">wss://sip.irl.coop:7443</code>
          </p>
        </div>
        {status === "ready" && config && (
          <div className="flex items-center gap-2.5">
            <MemberAvatar
              sub={config.profileUserID}
              avatar={config.avatar}
              name={config.fullname}
              className="size-8"
            />
            <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/10 px-2.5 py-1 text-xs font-medium text-emerald-700 dark:text-emerald-400">
              <Radio className="h-3.5 w-3.5" />
              {config.extension}
            </span>
          </div>
        )}
        {isPlatformAdmin && (
          <Button asChild size="sm" variant="outline">
            <a href={PBX_ADMIN_URL} target="_blank" rel="noreferrer">
              <Settings2 className="me-1.5 h-3.5 w-3.5" />
              Manage PBX
            </a>
          </Button>
        )}
      </div>

      <div className="flex-1 overflow-hidden p-0">
        {status === "loading" && (
          <div className="flex h-full items-center justify-center">
            <Skeleton className="h-[560px] w-full max-w-md rounded-none" />
          </div>
        )}

        {status === "error" && (
          <div className="flex h-full flex-col items-center justify-center gap-3 p-6 text-center">
            <Phone className="h-8 w-8 text-muted-foreground" />
            <p className="text-sm text-muted-foreground">
              {error ?? "Could not load your SIP configuration."}
            </p>
            <Button size="sm" onClick={load}>
              <RefreshCw className="me-2 h-3.5 w-3.5" />
              Retry
            </Button>
          </div>
        )}

        {status === "ready" && config && (
          <iframe
            src="/phone/index.html"
            title="Browser Phone"
            className="block h-full w-full border-0"
            allow="microphone; camera; autoplay; display-capture"
            allowFullScreen
          />
        )}
      </div>
    </div>
  )
}
