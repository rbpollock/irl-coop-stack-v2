"use client"

import { zodResolver } from "@hookform/resolvers/zod"
import { useForm } from "react-hook-form"

import type { DeleteAccountFormType, UserType } from "../../../types"

import { DeleteAccountSchema } from "../../_schemas/delete-account-schema"

import { ButtonLoading } from "@/components/ui/button"

export function DeleteAccountForm({ user }: { user: UserType }) {
  const form = useForm<DeleteAccountFormType>({
    resolver: zodResolver(DeleteAccountSchema),
    defaultValues: {
      ...user,
    },
  })

  const { isSubmitting } = form.formState

  return (
    <div className="flex gap-x-2">
      <ButtonLoading isLoading={isSubmitting} variant="outline">
        Disable Account
      </ButtonLoading>
      <ButtonLoading isLoading={isSubmitting} variant="destructive">
        Delete Account
      </ButtonLoading>
    </div>
  )
}
