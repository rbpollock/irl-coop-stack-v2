"use client"

import { zodResolver } from "@hookform/resolvers/zod"
import { useForm } from "react-hook-form"

import type { z } from "zod"

import { FormLayoutsSchema } from "../../_schemas/form-layouts-schema"

import { ButtonLoading } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { InputPhone } from "@/components/ui/input-phone"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

type FormType = z.infer<typeof FormLayoutsSchema>

export function HorizontalFormLayout() {
  const form = useForm<FormType>({
    resolver: zodResolver(FormLayoutsSchema),
  })

  const { isSubmitting, isDirty } = form.formState
  const isDisabled = isSubmitting || !isDirty

  async function onSubmit(_data: FormType) {}

  return (
    <Card>
      <CardHeader>
        <CardTitle>Horizontal Form Layout</CardTitle>
      </CardHeader>
      <CardContent>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="grid gap-y-3">
            <FormField
              control={form.control}
              name="firstName"
              render={({ field }) => (
                <FormItem className="grid grid-cols-8 items-center gap-x-3">
                  <FormLabel className="col-span-2 md:col-span-1">
                    First Name
                  </FormLabel>
                  <FormControl className="col-start-3 col-span-full md:col-start-2">
                    <Input type="text" placeholder="John" {...field} />
                  </FormControl>
                  <FormMessage className="col-start-3 col-span-full md:col-start-2" />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="lastName"
              render={({ field }) => (
                <FormItem className="grid grid-cols-8 items-center gap-x-3">
                  <FormLabel className="col-span-2 md:col-span-1">
                    Last Name
                  </FormLabel>
                  <FormControl className="col-start-3 col-span-full md:col-start-2">
                    <Input type="text" placeholder="Doe" {...field} />
                  </FormControl>
                  <FormMessage className="col-start-3 col-span-full md:col-start-2" />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="username"
              render={({ field }) => (
                <FormItem className="grid grid-cols-8 items-center gap-x-3">
                  <FormLabel className="col-span-2 md:col-span-1">
                    Username
                  </FormLabel>
                  <FormControl className="col-start-3 col-span-full md:col-start-2">
                    <Input type="text" placeholder="john_doe" {...field} />
                  </FormControl>
                  <FormMessage className="col-start-3 col-span-full md:col-start-2" />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="email"
              render={({ field }) => (
                <FormItem className="grid grid-cols-8 items-center gap-x-3">
                  <FormLabel className="col-span-2 md:col-span-1">
                    Email
                  </FormLabel>
                  <FormControl className="col-start-3 col-span-full md:col-start-2">
                    <Input
                      type="email"
                      placeholder="name@example.com"
                      {...field}
                    />
                  </FormControl>
                  <FormMessage className="col-start-3 col-span-full md:col-start-2" />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="phoneNumber"
              render={({ field }) => (
                <FormItem className="grid grid-cols-8 items-center gap-x-3">
                  <FormLabel className="col-span-2 md:col-span-1">
                    Phone Number
                  </FormLabel>
                  <FormControl className="col-start-3 col-span-full md:col-start-2">
                    <InputPhone placeholder="+123 4567890" {...field} />
                  </FormControl>
                  <FormMessage className="col-start-3 col-span-full md:col-start-2" />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="state"
              render={({ field }) => (
                <FormItem className="grid grid-cols-8 items-center gap-x-3">
                  <FormLabel className="col-span-2 md:col-span-1">
                    State
                  </FormLabel>
                  <FormControl>
                    <Select
                      onValueChange={field.onChange}
                      defaultValue={field.value}
                    >
                      <SelectTrigger className="col-start-3 col-span-full md:col-start-2">
                        <SelectValue placeholder="Select a state" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="california">California</SelectItem>
                        <SelectItem value="texas">Texas</SelectItem>
                        <SelectItem value="florida">Florida</SelectItem>
                        <SelectItem value="new-york">New York</SelectItem>
                      </SelectContent>
                    </Select>
                  </FormControl>
                  <FormMessage className="col-start-3 col-span-full md:col-start-2" />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="country"
              render={({ field }) => (
                <FormItem className="grid grid-cols-8 items-center gap-x-3">
                  <FormLabel className="col-span-2 md:col-span-1">
                    Country
                  </FormLabel>
                  <FormControl className="col-start-3 col-span-full md:col-start-2">
                    <Input type="text" placeholder="USA" {...field} />
                  </FormControl>
                  <FormMessage className="col-start-3 col-span-full md:col-start-2" />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="address"
              render={({ field }) => (
                <FormItem className="grid grid-cols-8 items-center gap-x-3">
                  <FormLabel className="col-span-2 md:col-span-1">
                    Address
                  </FormLabel>
                  <FormControl className="col-start-3 col-span-full md:col-start-2">
                    <Input type="text" placeholder="123 Main St" {...field} />
                  </FormControl>
                  <FormMessage className="col-start-3 col-span-full md:col-start-2" />
                </FormItem>
              )}
            />

            <ButtonLoading
              isLoading={isSubmitting}
              disabled={isDisabled}
              className="w-fit mt-2"
            >
              Save
            </ButtonLoading>
          </form>
        </Form>
      </CardContent>
    </Card>
  )
}
