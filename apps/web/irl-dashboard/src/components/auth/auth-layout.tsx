"use client"

import Link from "next/link"
import { useParams } from "next/navigation"

import type { DictionaryType } from "@/lib/get-dictionary"
import type { LocaleType } from "@/types"
import type { ComponentProps } from "react"

import { ensureLocalizedPathname } from "@/lib/i18n"
import { cn } from "@/lib/utils"

import { LanguageDropdown } from "../language-dropdown"

interface AuthProps extends ComponentProps<"div"> {
  imgSrc?: string
  imgClassName?: string
  dictionary: DictionaryType
}

export function Auth({
  className,
  children,
  imgSrc,
  imgClassName,
  dictionary,
  ...props
}: AuthProps) {
  const params = useParams()
  const locale = params.lang as LocaleType

  return (
    <section
      className={cn(
        "container min-h-screen w-full flex justify-between px-0",
        className
      )}
      {...props}
    >
      <div className="flex-1 relative grid">
        <div className="absolute top-0 inset-x-0 flex justify-between items-center px-4 py-2.5">
          <Link
            href={ensureLocalizedPathname("/", locale)}
            className="flex text-foreground font-black z-50"
          >
            <span className="flex size-6 items-center justify-center rounded-md bg-primary text-primary-foreground text-xs font-bold">
              i
            </span>
            <span>irl.coop</span>
          </Link>
          <LanguageDropdown dictionary={dictionary} />
        </div>
        <div className="max-w-[28rem] w-full m-auto px-6 py-12 space-y-6">
          {children}
        </div>
      </div>
      {imgSrc && <AuthImage imgSrc={imgSrc} className={cn("", imgClassName)} />}
    </section>
  )
}

interface AuthImageProps extends ComponentProps<"div"> {
  imgSrc: string
}

export function AuthImage({ className, imgSrc, ...props }: AuthImageProps) {
  return (
    <div
      className={cn(
        "basis-1/2 relative hidden min-h-screen bg-muted md:block",
        className
      )}
      {...props}
    >
      <img
        src={imgSrc}
        alt=""
        className="absolute inset-0 size-full object-cover"
      />
    </div>
  )
}

export function AuthHeader({ className, ...props }: ComponentProps<"div">) {
  return <div className={cn("space-y-2 text-center", className)} {...props} />
}

export function AuthTitle({ className, ...props }: ComponentProps<"h1">) {
  return (
    <h1
      className={cn(
        "text-2xl font-semibold leading-none tracking-tight",
        className
      )}
      {...props}
    />
  )
}

export function AuthDescription({ className, ...props }: ComponentProps<"p">) {
  return (
    <p className={cn("text-sm text-muted-foreground", className)} {...props} />
  )
}

export function AuthForm({ className, ...props }: ComponentProps<"div">) {
  return <div className={className} {...props} />
}

export function AuthFooter({ className, ...props }: ComponentProps<"div">) {
  return <div className={cn("grid gap-6", className)} {...props} />
}
