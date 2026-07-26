"use client"

import { zodResolver } from "@hookform/resolvers/zod"
import { useForm } from "react-hook-form"
import { Search } from "lucide-react"

import type { EmailListSearchFormType } from "../types"

import { EmailListSearchSchema } from "../_schemas/email-list-search-schema"

import { useEmailContext } from "../_hooks/use-email-context"
import { Form, FormControl, FormField, FormItem } from "@/components/ui/form"
import { Input } from "@/components/ui/input"

interface EmailListSearchFormProps {
  pageQuery: number
  filterParam: string
}

export function EmailListSearchForm({
  pageQuery,
  filterParam,
}: EmailListSearchFormProps) {
  const { handleGetFilteredEmailsBySearchTerm } = useEmailContext()
  const form = useForm<EmailListSearchFormType>({
    resolver: zodResolver(EmailListSearchSchema),
    defaultValues: {
      term: "",
    },
  })

  const onSubmit = async (data: EmailListSearchFormType) => {
    handleGetFilteredEmailsBySearchTerm(data.term, filterParam, pageQuery)
  }

  return (
    <Form {...form}>
      <form onChange={form.handleSubmit(onSubmit)} className="grow">
        <FormField
          control={form.control}
          name="term"
          render={({ field }) => (
            <FormItem className="relative space-y-0">
              <Search className="absolute start-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <FormControl>
                <Input
                  className="w-full bg-muted ps-9"
                  placeholder="Search..."
                  type="search"
                  {...field}
                />
              </FormControl>
            </FormItem>
          )}
        />
      </form>
    </Form>
  )
}
