"use client"

import { useRef, useState } from "react"
import { useSession } from "next-auth/react"
import { toast } from "sonner"
import { Camera, Loader2 } from "lucide-react"

import { cn } from "@/lib/utils"

import { Button } from "@/components/ui/button"

const COOP_API_URL =
  process.env.NEXT_PUBLIC_COOP_API_URL ?? "https://api.irl.coop"

// Replaces the member's DiceBear default with a custom image: pick a file,
// PUT it to coop-api (Bearer), which stores it in MinIO and persists the
// avatar URL on the profile. `onSuccess` lets the host re-fetch the profile.
export function ChangeAvatar({
  onSuccess,
  className,
}: {
  onSuccess?: () => void
  className?: string
}) {
  const { data: session } = useSession()
  const inputRef = useRef<HTMLInputElement>(null)
  const [uploading, setUploading] = useState(false)

  async function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    e.target.value = ""
    if (!file || !session?.accessToken) return
    setUploading(true)
    try {
      const form = new FormData()
      form.append("avatar", file)
      const res = await fetch(`${COOP_API_URL}/api/v1/profile/avatar`, {
        method: "PUT",
        headers: { Authorization: `Bearer ${session.accessToken}` },
        body: form,
      })
      if (!res.ok) {
        const body = (await res.json().catch(() => ({}))) as { error?: string }
        throw new Error(body.error ?? `Upload failed (${res.status})`)
      }
      toast.success("Profile photo updated")
      onSuccess?.()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Upload failed")
    } finally {
      setUploading(false)
    }
  }

  return (
    <>
      <input
        ref={inputRef}
        type="file"
        accept="image/png,image/jpeg,image/webp,image/gif"
        className="hidden"
        onChange={onFile}
      />
      <Button
        type="button"
        variant="secondary"
        size="icon"
        aria-label="Change profile photo"
        onClick={() => inputRef.current?.click()}
        disabled={uploading}
        className={cn("rounded-full shadow-sm", className)}
      >
        {uploading ? (
          <Loader2 className="size-4 animate-spin" />
        ) : (
          <Camera className="size-4" />
        )}
      </Button>
    </>
  )
}
