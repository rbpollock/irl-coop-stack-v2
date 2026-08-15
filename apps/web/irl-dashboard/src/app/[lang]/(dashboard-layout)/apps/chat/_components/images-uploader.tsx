"use client"

import { useState } from "react"
import { zodResolver } from "@hookform/resolvers/zod"
import { useForm } from "react-hook-form"
import { Image, Send } from "lucide-react"

import type { ImagesUploaderFormType } from "../types"

import { ImagesUploaderSchema } from "../_schemas/images-uploader-schema"

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
import { MAX_IMAGES, MAX_IMAGE_SIZE } from "../constants"

const formattedImageSize = formatFileSize(MAX_IMAGE_SIZE)

export function ImagesUploader() {
  const { handleAddImagesMessage } = useChatContext()
  const [isOpen, setIsOpen] = useState(false)

  const form = useForm<ImagesUploaderFormType>({
    resolver: zodResolver(ImagesUploaderSchema),
    defaultValues: { images: [] },
  })

  const { isSubmitting } = form.formState

  const onSubmit = async (data: ImagesUploaderFormType) => {
    handleAddImagesMessage(data.images)

    // Reset to default
    form.reset()
    setIsOpen(false)
  }

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogTrigger asChild>
        <Button variant="ghost" size="icon">
          <Image className="h-4 w-4" aria-label="Images" />
        </Button>
      </DialogTrigger>
      <DialogContent className="rounded-lg" aria-describedby={undefined}>
        <DialogHeader>
          <DialogTitle>Send Images</DialogTitle>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="grid">
            <FormField
              control={form.control}
              name="images"
              render={({ field }) => (
                <FormItem>
                  <FileDropzone
                    onFilesChange={field.onChange}
                    multiple
                    accept={{ "image/*": [] }}
                    maxSize={MAX_IMAGE_SIZE}
                    maxFiles={MAX_IMAGES}
                    {...field}
                  />
                  <FormDescription>
                    Select up to {MAX_IMAGES} images, with a maximum image size
                    of {formattedImageSize} per image.
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
