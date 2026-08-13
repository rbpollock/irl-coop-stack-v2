"use client"

import { useEffect, useState } from "react"
import { useSession } from "next-auth/react"
import {
  AlertCircle,
  Check,
  CheckCircle,
  Copy,
  RefreshCw,
  Shield,
} from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"

const COOP_API_URL =
  process.env.NEXT_PUBLIC_COOP_API_URL ?? "https://api.irl.coop"

export function SafeWallet() {
  const { data: session } = useSession()
  const [safeAddress, setSafeAddress] = useState<string | null>(null)
  const [deployed, setDeployed] = useState<boolean | null>(null)
  const [loading, setLoading] = useState(false)
  const [deploying, setSaving] = useState(false)
  const [copied, setCopied] = useState(false)
  const [txHash, setTxHash] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const token = session?.accessToken as string | undefined
  const userId = session?.user?.id as string | undefined

  // Convert UUID to a deterministic saltNonce bigint string
  const saltNonce = userId
    ? BigInt("0x" + userId.replace(/-/g, "")).toString()
    : null

  useEffect(() => {
    if (!token || !saltNonce) return
    setLoading(true)
    fetch(`${COOP_API_URL}/api/safe/predict`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ saltNonce }),
    })
      .then((res) => {
        if (!res.ok)
          throw new Error(`Failed to predict address (${res.status})`)
        return res.json()
      })
      .then((data) => {
        setSafeAddress(data.safeAddress)
        setDeployed(data.deployed)
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [token, saltNonce])

  const copyToClipboard = () => {
    if (!safeAddress) return
    navigator.clipboard.writeText(safeAddress)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleDeploy = async () => {
    if (!token || !saltNonce) return
    setSaving(true)
    setError(null)
    try {
      const res = await fetch(`${COOP_API_URL}/api/safe/deploy`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ saltNonce }),
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data.error ?? `Deployment failed (${res.status})`)
      }
      const data = await res.json()
      setDeployed(true)
      setTxHash(data.txHash)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setSaving(false)
    }
  }

  if (!userId) return null

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Shield className="h-4 w-4" />
          Cooperative Safe Wallet
        </CardTitle>
        <CardDescription>
          Your sovereign smart contract account on the Base-native node.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {loading && (
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <RefreshCw className="h-3 w-3 animate-spin" />
            Calculating predicted Safe address...
          </div>
        )}

        {!loading && safeAddress && (
          <div className="space-y-4">
            <div>
              <div className="text-xs font-medium text-muted-foreground">
                Safe Account Address
              </div>
              <div className="mt-1.5 flex items-center gap-2">
                <code className="rounded bg-muted px-2 py-1 text-xs font-mono">
                  {safeAddress}
                </code>
                <Button
                  size="icon"
                  variant="ghost"
                  className="h-7 w-7"
                  onClick={copyToClipboard}
                >
                  {copied ? (
                    <Check className="h-3.5 w-3.5 text-emerald-500" />
                  ) : (
                    <Copy className="h-3.5 w-3.5" />
                  )}
                </Button>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-xs font-medium text-muted-foreground">
                Status:
              </span>
              {deployed ? (
                <span className="inline-flex items-center gap-1 rounded bg-emerald-500/10 px-2 py-0.5 text-xs font-medium text-emerald-700">
                  <CheckCircle className="h-3.5 w-3.5" />
                  Deployed (Active)
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 rounded bg-amber-500/10 px-2 py-0.5 text-xs font-medium text-amber-700">
                  <AlertCircle className="h-3.5 w-3.5" />
                  Not Deployed (Inactive)
                </span>
              )}
            </div>

            {!deployed && (
              <div>
                <Button
                  size="sm"
                  onClick={handleDeploy}
                  disabled={deploying}
                  className="mt-1"
                >
                  {deploying ? (
                    <>
                      <RefreshCw className="mr-2 h-3.5 w-3.5 animate-spin" />
                      Deploying Safe...
                    </>
                  ) : (
                    "Deploy Safe"
                  )}
                </Button>
              </div>
            )}

            {txHash && (
              <div className="rounded border border-emerald-300/30 bg-emerald-500/5 p-3 text-xs text-emerald-800">
                <p className="font-semibold">Safe Deployed successfully!</p>
                <p className="mt-1 font-mono">Tx Hash: {txHash}</p>
              </div>
            )}

            {error && (
              <div className="rounded border border-destructive/30 bg-destructive/5 p-3 text-xs text-destructive">
                {error}
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
