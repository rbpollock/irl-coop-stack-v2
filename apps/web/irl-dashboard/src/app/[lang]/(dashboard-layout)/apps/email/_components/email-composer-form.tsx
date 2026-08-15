"use client"

import { useState } from "react"
import { zodResolver } from "@hookform/resolvers/zod"
import { useForm } from "react-hook-form"
import { ListRestart, MoreVertical, Send } from "lucide-react"

import type { EmailComposerFormType } from "../types"

import { EmailComposerSchema } from "../_schemas/email-composer-schema"

import { Button, ButtonLoading } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Editor } from "@/components/ui/editor"
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { Separator } from "@/components/ui/separator"
import { Toggle } from "@/components/ui/toggle"

export function EmailComposerForm() {
  const [showCc, setShowCc] = useState(false)
  const [showBcc, setShowBcc] = useState(false)

  const form = useForm<EmailComposerFormType>({
    resolver: zodResolver(EmailComposerSchema),
    defaultValues: {
      to: "",
      cc: "",
      bcc: "",
      subject: "",
      content: "",
    },
  })

  const { isSubmitting } = form.formState

  function onSubmit(_data: EmailComposerFormType) {}

  return (
    <Form {...form}>
      <form
        onSubmit={form.handleSubmit(onSubmit)}
        className="h-full flex flex-col justify-between gap-3"
      >
        <div className="px-3 space-y-2">
          <div className="flex items-center justify-between gap-2">
            <FormField
              control={form.control}
              name="to"
              render={({ field }) => (
                <FormItem className="grow space-y-0">
                  <FormControl>
                    <Input type="email" placeholder="To" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <div className="flex items-center gap-2">
              <Toggle
                pressed={showCc}
                onPressedChange={() => setShowCc(!showCc)}
              >
                Cc
              </Toggle>
              <Separator orientation="vertical" className="h-4" />
              <Toggle
                pressed={showBcc}
                onPressedChange={() => setShowBcc(!showBcc)}
              >
                Bcc
              </Toggle>
            </div>
          </div>
          {showCc && (
            <FormField
              control={form.control}
              name="cc"
              render={({ field }) => (
                <FormItem>
                  <FormControl>
                    <Input type="email" placeholder="Cc" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          )}
          {showBcc && (
            <FormField
              control={form.control}
              name="bcc"
              render={({ field }) => (
                <FormItem>
                  <FormControl>
                    <Input type="email" placeholder="Bcc" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          )}
          <FormField
            control={form.control}
            name="subject"
            render={({ field }) => (
              <FormItem>
                <FormControl>
                  <Input type="text" placeholder="Subject" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="content"
            render={({ field }) => (
              <FormItem className="space-y-0">
                <FormControl>
                  <Editor
                    placeholder="Write your message here..."
                    onValueChange={field.onChange}
                    className="h-[12.5rem]"
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
        </div>
        <div className="flex justify-between items-center p-3 border-t border-border">
          <div className="flex items-center gap-2">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button type="button" variant="ghost" size="icon">
                  <MoreVertical className="h-4 w-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="start">
                <DropdownMenuItem>Save as draft</DropdownMenuItem>
                <DropdownMenuItem>Add label</DropdownMenuItem>
                <DropdownMenuItem>Plain text mode</DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
            <Button
              type="reset"
              variant="ghost"
              size="icon"
              onClick={() => form.reset()}
            >
              <ListRestart className="h-4 w-4" />
            </Button>
          </div>

          <ButtonLoading
            isLoading={isSubmitting}
            size="icon"
            icon={Send}
            iconClassName="me-0"
            loadingIconClassName="me-0"
          />
        </div>
      </form>
    </Form>
  )
}
