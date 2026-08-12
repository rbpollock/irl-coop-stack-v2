"use client"

import Link from "next/link"
import { useSession } from "next-auth/react"
import { ArrowRight, KeyRound } from "lucide-react"

import { buttonVariants } from "@/components/ui/button"

function timeOfDay(): string {
  const hour = new Date().getHours()
  if (hour < 12) return "Good morning"
  if (hour < 18) return "Good afternoon"
  return "Good evening"
}

// A greeting from the coop, tailored to the member's status: the canonical
// identity is the one thing that gates their mailbox, so it gets the CTA.
export function CoopGreeting() {
  const { data: session } = useSession()
  const name = session?.user?.name || "co-op member"
  const email = session?.user?.email || ""
  const hasCanonicalIdentity = email.endsWith("@irl.coop")

  return (
    <div className="col-span-full flex flex-col gap-4 rounded-xl border bg-card p-6 shadow-sm md:flex-row md:items-center md:justify-between">
      <div>
        <h2 className="text-2xl font-black tracking-tight">
          {timeOfDay()}, {name}.
        </h2>
        <p className="mt-1 text-muted-foreground">
          {hasCanonicalIdentity ? (
            <>Welcome back to the coop — one identity, every app.</>
          ) : (
            <>
              You&apos;re signed in as{" "}
              <span className="font-medium">{email}</span>. Claim your @irl.coop
              username to unlock your mailbox and a single address across the
              coop.
            </>
          )}
        </p>
      </div>
      {!hasCanonicalIdentity && (
        <Link href="/apps/webmail" className={buttonVariants({ size: "sm" })}>
          <KeyRound className="size-4" />
          Claim your username
          <ArrowRight className="size-4" />
        </Link>
      )}
    </div>
  )
}
