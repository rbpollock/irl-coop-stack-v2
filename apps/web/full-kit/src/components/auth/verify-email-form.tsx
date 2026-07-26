"use client"

import Link from "next/link"
import { useParams } from "next/navigation"
import { zodResolver } from "@hookform/resolvers/zod"
import { useForm } from "react-hook-form"

import type { LocaleType, VerifyEmailFormType } from "@/types"

import { VerifyEmailSchema } from "@/schemas/verify-email-schema"

import { ensureLocalizedPathname } from "@/lib/i18n"
import { cn } from "@/lib/utils"

import { toast } from "@/hooks/use-toast"
import { buttonVariants } from "@/components/ui/button"
import { Form } from "@/components/ui/form"

export function VerifyEmailForm() {
  const params = useParams()
  const form = useForm<VerifyEmailFormType>({
    resolver: zodResolver(VerifyEmailSchema),
    defaultValues: {
      email: "",
    },
  })

  const locale = params.lang as LocaleType

  async function onSubmit(data: VerifyEmailFormType) {
    try {
      const response = await fetch("/api/auth/verify-email", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(data),
      })

      if (!response.ok) {
        throw new Error("Failed to send verification email")
      }

      toast({
        title: "Check your email",
        description:
          "We've sent you an email with instructions to verify your email address.",
      })
    } catch (error) {
      toast({
        variant: "destructive",
        title: "Something went wrong",
        description: error instanceof Error ? error.message : undefined,
      })
    }
  }

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="grid gap-2">
        <Link
          href={ensureLocalizedPathname(
            process.env.NEXT_PUBLIC_HOME_PATHNAME || "/",
            locale
          )}
          className={cn(buttonVariants({ variant: "default" }))}
        >
          Skip for now
        </Link>
        <div className="text-center text-sm">
          Didn&apos;t receive the email?{" "}
          <Link href="" className="underline">
            Resend
          </Link>
        </div>
      </form>
    </Form>
  )
}
