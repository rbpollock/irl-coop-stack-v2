"use client"

import { formatFileSize } from "@/lib/utils"

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { FileDropzone } from "@/components/ui/file-dropzone"

export function FileDropzoneMaxSize() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>File Dropzone Max Size</CardTitle>
        <CardDescription>Set to max {formatFileSize(250000)}</CardDescription>
      </CardHeader>
      <CardContent className="flex items-center justify-center">
        <FileDropzone multiple maxSize={250000} />
      </CardContent>
    </Card>
  )
}
