"use client"

import { useEffect } from "react"
import { zodResolver } from "@hookform/resolvers/zod"
import { useForm } from "react-hook-form"
import { Grid2x2Plus } from "lucide-react"

import type { KanbanColumnFormType } from "../../types"

import { KanbanColumnSchema } from "../../_schemas/kanban-column-schema"

import { useKanbanContext } from "../../_hooks/use-kanban-context"
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
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"

const defaultValues = {
  title: "",
}

export function KanbanAddColumnSidebar() {
  const {
    kanbanAddColumnSidebarIsOpen,
    setKanbanAddColumnSidebarIsOpen,
    handleAddColumn,
  } = useKanbanContext()

  const form = useForm<KanbanColumnFormType>({
    resolver: zodResolver(KanbanColumnSchema),
    defaultValues,
  })

  // Reset the form whenever `kanbanAddColumnSidebarIsOpen` changes
  useEffect(() => {
    form.reset()
  }, [kanbanAddColumnSidebarIsOpen, form])

  const { isSubmitting, isDirty } = form.formState
  const isDisabled = isSubmitting || !isDirty // Disable button if form is unchanged or submitting

  function onSubmit(data: KanbanColumnFormType) {
    handleAddColumn(data)

    handleSidebarClose()
  }

  const handleSidebarClose = () => {
    form.reset(defaultValues) // Reset the form to the initial values
    setKanbanAddColumnSidebarIsOpen(false) // Close the sidebar
  }

  return (
    <Sheet
      open={kanbanAddColumnSidebarIsOpen}
      onOpenChange={() => handleSidebarClose()}
    >
      <SheetContent className="p-0" side="end">
        <ScrollArea className="h-full p-4">
          <SheetHeader>
            <SheetTitle>Add New Column</SheetTitle>
            <SheetDescription>Add a new column to the board.</SheetDescription>
          </SheetHeader>
          <Form {...form}>
            <form
              onSubmit={form.handleSubmit(onSubmit)}
              className="grid gap-y-3 mt-3"
            >
              <FormField
                control={form.control}
                name="title"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Title</FormLabel>
                    <FormControl>
                      <Input placeholder="Column title" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <ButtonLoading
                isLoading={isSubmitting}
                disabled={isDisabled}
                className="w-full"
                icon={Grid2x2Plus}
              >
                Save
              </ButtonLoading>
            </form>
          </Form>
        </ScrollArea>
      </SheetContent>
    </Sheet>
  )
}
