"use client"

import { useEffect } from "react"
import { zodResolver } from "@hookform/resolvers/zod"
import { useForm } from "react-hook-form"
import { Grid2x2Plus } from "lucide-react"

import type { KanbanTaskFormType } from "../../types"

import { labelsData } from "../../_data/labels"

import { KanbanTaskSchema } from "../../_schemas/kanban-task-schema"

import { useKanbanContext } from "../../_hooks/use-kanban-context"
import { ButtonLoading } from "@/components/ui/button"
import { DatePicker } from "@/components/ui/date-picker"
import { FileDropzone } from "@/components/ui/file-dropzone"
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { InputTagsWithSuggestions } from "@/components/ui/input-tags"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { Textarea } from "@/components/ui/textarea"

const defaultValues = {
  title: "",
  description: "",
  label: "Development",
  dueDate: new Date(),
  assigned: [],
  comments: [],
  attachments: [],
}

export function KanbanUpdateTaskSidebar() {
  const {
    kanbanState,
    kanbanUpdateTaskSidebarIsOpen,
    setKanbanUpdateTaskSidebarIsOpen,
    handleUpdateTask,
    handleSelectTask,
  } = useKanbanContext()

  const form = useForm<KanbanTaskFormType>({
    resolver: zodResolver(KanbanTaskSchema),
    defaultValues,
  })

  const { teamMembers, selectedTask } = kanbanState
  const { isSubmitting, isDirty } = form.formState
  const isDisabled = isSubmitting || !isDirty // Disable button if form is unchanged or submitting

  // Reset the form with the current selected task's values whenever `selectedTask` changes
  useEffect(() => {
    if (selectedTask) {
      form.reset({
        title: selectedTask?.title,
        description: selectedTask?.description,
        label: selectedTask?.label,
        assigned: selectedTask?.assigned || [],
        comments: selectedTask?.comments || [],
        dueDate: selectedTask?.dueDate,
        attachments: selectedTask?.attachments || [],
      })
    }
  }, [selectedTask, form])

  function onSubmit(data: KanbanTaskFormType) {
    if (selectedTask) {
      handleUpdateTask({
        ...data,
        id: selectedTask.id,
        columnId: selectedTask.columnId,
        order: selectedTask.order,
        comments: selectedTask.comments,
      })
    }

    handleSidebarClose()
  }

  const handleSidebarClose = () => {
    form.reset(defaultValues) // Reset the form to the initial values
    handleSelectTask(undefined) // Unselect the current task
    setKanbanUpdateTaskSidebarIsOpen(false) // Close the sidebar
  }

  return (
    <Sheet
      open={kanbanUpdateTaskSidebarIsOpen}
      onOpenChange={() => handleSidebarClose()}
    >
      <SheetContent className="p-0" side="end">
        <ScrollArea className="h-full p-4">
          <SheetHeader>
            <SheetTitle>Update Task</SheetTitle>
            <SheetDescription>
              Modify the details of the {selectedTask?.title} task.
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
                      <Input placeholder="Task title" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="label"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Label</FormLabel>
                    <Select
                      onValueChange={field.onChange}
                      defaultValue={field.value}
                    >
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder="Select a label" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {labelsData.map((label) => (
                          <SelectItem key={label.id} value={label.name}>
                            {label.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="assigned"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Assigned Team Members</FormLabel>
                    <FormControl>
                      <InputTagsWithSuggestions
                        suggestions={teamMembers.map(({ name }) => name)}
                        tags={field.value.map(({ name }) => name)}
                        onTagsChange={(tags) =>
                          field.onChange(
                            teamMembers.filter((member) =>
                              tags.includes(member.name)
                            )
                          )
                        }
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="dueDate"
                render={({ field }) => (
                  <FormItem className="flex flex-col">
                    <FormLabel>Due Date</FormLabel>
                    <FormControl>
                      <DatePicker
                        formatStr="PPP"
                        onValueChange={field.onChange}
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="description"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Description</FormLabel>
                    <FormControl>
                      <Textarea
                        placeholder="Event description"
                        className="resize-none"
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="attachments"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Attachments</FormLabel>
                    <FormControl>
                      <FileDropzone
                        multiple
                        onFilesChange={field.onChange}
                        {...field}
                      />
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
