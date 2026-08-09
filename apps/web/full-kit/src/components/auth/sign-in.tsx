"use client"

import Link from "next/link"
import { useParams, useSearchParams } from "next/navigation"
import { signIn } from "next-auth/react"
import { SiGoogle } from "react-icons/si"

import type { DictionaryType } from "@/lib/get-dictionary"
import type { LocaleType } from "@/types"

import { ensureLocalizedPathname } from "@/lib/i18n"

import { buttonVariants } from "@/components/ui/button"

import {
  Auth,
  AuthDescription,
  AuthForm,
  AuthHeader,
  AuthTitle,
} from "./auth-layout"

function SignInButton({
  provider,
  label,
  icon: Icon,
  className,
}: {
  provider: string
  label: string
  icon: React.ComponentType<{ className?: string }>
  className?: string
}) {
  const searchParams = useSearchParams()
  const redirectPathname =
    searchParams.get("redirectTo") ||
    process.env.NEXT_PUBLIC_HOME_PATHNAME ||
    "/"

  return (
    <button
      type="button"
      onClick={() => signIn(provider, { callbackUrl: redirectPathname })}
      className={buttonVariants({
        variant: "outline",
        className: `w-full gap-3 ${className ?? ""}`,
      })}
    >
      <Icon className="size-5 shrink-0" />
      <span>{label}</span>
    </button>
  )
}

export function SignIn({ dictionary }: { dictionary: DictionaryType }) {
  const params = useParams()
  const locale = params.lang as LocaleType

  return (
    <Auth
      imgSrc="/images/illustrations/misc/welcome.svg"
      dictionary={dictionary}
    >
      <AuthHeader>
        <AuthTitle>Welcome to irl.coop</AuthTitle>
        <AuthDescription>
          Sign in to access the cooperative dashboard
        </AuthDescription>
      </AuthHeader>
      <AuthForm>
        <div className="grid gap-4">
          <SignInButton
            provider="coop-api"
            label="Continue with Google"
            icon={SiGoogle}
          />

          <div className="relative">
            <div className="absolute inset-0 flex items-center">
              <span className="w-full border-t" />
            </div>
            <div className="relative flex justify-center text-xs uppercase">
              <span className="bg-background px-2 text-muted-foreground">
                More options coming soon
              </span>
            </div>
          </div>

          <div className="flex justify-center gap-4 opacity-50">
            <span className="inline-flex items-center gap-1 text-sm text-muted-foreground">
              <svg className="size-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M22 2 11 13" /><path d="m22 2-7 20-4-9-9-4Z" /></svg>
              SMS
            </span>
            <span className="inline-flex items-center gap-1 text-sm text-muted-foreground">
              <svg className="size-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect width="20" height="14" x="2" y="3" rx="2" /><path d="M8 21h8" /><path d="M12 17v4" /></svg>
              Passkey
            </span>
          </div>
        </div>
      </AuthForm>
    </Auth>
  )
}
