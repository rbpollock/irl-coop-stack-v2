"use client"

import { zodResolver } from "@hookform/resolvers/zod"
import { useForm } from "react-hook-form"

import type { ComingSoonFormType } from "@/types"

import { ComingSoonSchema } from "@/schemas/coming-soon-schema"

import { toast } from "@/hooks/use-toast"
import { ButtonLoading } from "@/components/ui/button"
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"

const defaultValues = { email: "" }

export function ComingSoonForm() {
  const form = useForm<ComingSoonFormType>({
    resolver: zodResolver(ComingSoonSchema),
    defaultValues,
  })

  const { isSubmitting } = form.formState

  async function onSubmit(_data: ComingSoonFormType) {
    form.reset(defaultValues) // Reset the form to the initial state

    toast({
      title: "Thank you for subscribing!",
      description: "We'll notify you when we launch.",
    })
  }

  return (
    <Form {...form}>
      <form
        onSubmit={form.handleSubmit(onSubmit)}
        className="flex gap-x-2 justify-center text-start"
      >
        <FormField
          control={form.control}
          name="email"
          render={({ field }) => (
            <FormItem className="shrink-0 w-full space-y-0">
              <FormLabel className="sr-only">Email address</FormLabel>
              <FormControl>
                <Input
                  type="email"
                  placeholder="name@example.com"
                  className="bg-background"
                  {...field}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <ButtonLoading isLoading={isSubmitting}>Notify Me</ButtonLoading>
      </form>
    </Form>
  )
}
