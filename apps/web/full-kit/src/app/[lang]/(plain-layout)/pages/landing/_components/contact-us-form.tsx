"use client"

import { zodResolver } from "@hookform/resolvers/zod"
import { useForm } from "react-hook-form"

import type { ContactUsType } from "../types"

import { ContactUsSchema } from "../_schemas/contact-us-schema"

import { toast } from "@/hooks/use-toast"
import { ButtonLoading } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"

export function ContactUsForm() {
  const form = useForm<ContactUsType>({
    resolver: zodResolver(ContactUsSchema),
    defaultValues: {
      name: "",
      email: "",
      message: "",
    },
  })

  const { isSubmitting } = form.formState

  async function onSubmit(_data: ContactUsType) {
    toast({
      title: "Success",
      description: "Your message has been sent successfully!",
    })
  }

  return (
    <Form {...form}>
      <Card asChild>
        <form
          onSubmit={form.handleSubmit(onSubmit)}
          className="grid gap-6 p-6 md:col-span-2"
        >
          <FormField
            control={form.control}
            name="name"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Name</FormLabel>
                <FormControl>
                  <Input type="text" placeholder="John Doe" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="email"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Email</FormLabel>
                <FormControl>
                  <Input
                    type="email"
                    placeholder="name@example.com"
                    {...field}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="message"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Message</FormLabel>
                <FormControl>
                  <Textarea className="min-h-[115px]" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <ButtonLoading isLoading={isSubmitting} size="lg">
            Submit
          </ButtonLoading>
        </form>
      </Card>
    </Form>
  )
}
