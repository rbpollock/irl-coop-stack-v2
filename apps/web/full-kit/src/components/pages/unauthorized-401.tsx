import Image from "next/image"
import Link from "next/link"

import type { LocaleType } from "@/types"

import { ensureLocalizedPathname } from "@/lib/i18n"

import { Button } from "@/components/ui/button"

export function Unauthorized401({ locale }: { locale: LocaleType }) {
  return (
    <div className="min-h-screen w-full flex flex-col items-center justify-center gap-y-6 text-center text-foreground bg-background p-4">
      <div className="flex flex-col-reverse justify-center items-center gap-y-6 md:flex-row md:text-start">
        <Image
          src="/images/illustrations/characters/character-03.svg"
          alt=""
          height={251}
          width={170}
          priority
        />
        <h1 className="inline-grid text-6xl font-black">
          401
          <span className="text-3xl font-semibold">Unauthorized Access</span>
        </h1>
      </div>
      <p className="max-w-prose text-xl text-muted-foreground">
        You don&apos;t have permission to access this page. If you&apos;re
        logged in, check your access or contact support.
      </p>
      <div className="flex gap-x-4">
        <Button size="lg" asChild>
          <Link href={ensureLocalizedPathname("/sign-in", locale)}>
            Sign In
          </Link>
        </Button>
        <Button variant="outline" size="lg" asChild>
          <Link href="/">Home Page</Link>
        </Button>
      </div>
    </div>
  )
}
