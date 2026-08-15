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

export function KanbanUpdateColumnSidebar() {
  const {
    kanbanState,
    kanbanUpdateColumnSidebarIsOpen,
    setKanbanUpdateColumnSidebarIsOpen,
    handleUpdateColumn,
    handleSelectColumn,
  } = useKanbanContext()

  const form = useForm<KanbanColumnFormType>({
    resolver: zodResolver(KanbanColumnSchema),
  })

  const selectedColumn = kanbanState.selectedColumn
  const { isSubmitting, isDirty } = form.formState
  const isDisabled = isSubmitting || !isDirty // Disable button if form is unchanged or submitting

  // Reset the form with the current selected column's values whenever `selectedColumn` changes
  useEffect(() => {
    if (selectedColumn) {
      form.reset({
        title: selectedColumn?.title,
      })
    }
  }, [selectedColumn, form])

  function onSubmit(data: KanbanColumnFormType) {
    if (selectedColumn) {
      handleUpdateColumn({
        title: data.title,
        id: selectedColumn.id,
        order: selectedColumn.order,
        tasks: selectedColumn.tasks,
      })
    }

    handleSidebarClose()
  }

  const handleSidebarClose = () => {
    form.reset(defaultValues) // Reset the form to the initial values
    handleSelectColumn(undefined) // Unselect the current column
    setKanbanUpdateColumnSidebarIsOpen(false) // Close the sidebar
  }

  return (
    <Sheet
      open={kanbanUpdateColumnSidebarIsOpen}
      onOpenChange={() => handleSidebarClose()}
    >
      <SheetContent className="p-0" side="end">
        <ScrollArea className="h-full p-4">
          <SheetHeader>
            <SheetTitle>Update Column</SheetTitle>
            <SheetDescription>
              Modify the details of the {selectedColumn?.title} column.
            </SheetDescription>
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
