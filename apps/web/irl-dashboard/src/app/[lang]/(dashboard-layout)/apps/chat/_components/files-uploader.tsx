"use client"

import { useState } from "react"
import { zodResolver } from "@hookform/resolvers/zod"
import { useForm } from "react-hook-form"
import { Paperclip, Send } from "lucide-react"

import type { FilesUploaderFormType } from "../types"

import { FilesUploaderSchema } from "../_schemas/files-uploader-schema"

import { formatFileSize } from "@/lib/utils"

import { useChatContext } from "../_hooks/use-chat-context"
import { Button, ButtonLoading } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { FileDropzone } from "@/components/ui/file-dropzone"
import {
  Form,
  FormDescription,
  FormField,
  FormItem,
  FormMessage,
} from "@/components/ui/form"
import { MAX_FILES, MAX_FILE_SIZE } from "../constants"

const formattedFileSize = formatFileSize(MAX_FILE_SIZE)

export function FilesUploader() {
  const { handleAddFilesMessage } = useChatContext()
  const [isOpen, setIsOpen] = useState(false)
  const form = useForm<FilesUploaderFormType>({
    resolver: zodResolver(FilesUploaderSchema),
    defaultValues: {
      files: [],
    },
  })

  const { isSubmitting } = form.formState

  const onSubmit = async (data: FilesUploaderFormType) => {
    handleAddFilesMessage(data.files)

    // Reset to default
    form.reset()
    setIsOpen(false)
  }

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogTrigger asChild>
        <Button variant="ghost" size="icon" className="relative">
          <Paperclip className="h-4 w-4" aria-label="Files" />
        </Button>
      </DialogTrigger>
      <DialogContent className="rounded-lg" aria-describedby={undefined}>
        <DialogHeader>
          <DialogTitle>Send Files</DialogTitle>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="w-full grid">
            <FormField
              control={form.control}
              name="files"
              render={({ field }) => (
                <FormItem className="space-y-0">
                  <FileDropzone
                    onFilesChange={field.onChange}
                    multiple
                    maxSize={MAX_FILE_SIZE}
                    maxFiles={MAX_FILES}
                    {...field}
                  />
                  <FormDescription>
                    Select up to {MAX_FILES} files, with a maximum file size of{" "}
                    {formattedFileSize} per file.
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />

            <ButtonLoading
              size="icon"
              isLoading={isSubmitting}
              className="ms-auto mt-2"
              icon={Send}
              iconClassName="me-0"
              loadingIconClassName="me-0"
            />
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}
