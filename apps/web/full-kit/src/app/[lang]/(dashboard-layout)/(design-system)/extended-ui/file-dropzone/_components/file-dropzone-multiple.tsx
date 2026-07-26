"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { FileDropzone } from "@/components/ui/file-dropzone"

export function FileDropzoneMultiple() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>File Dropzone Multiple</CardTitle>
      </CardHeader>
      <CardContent className="flex items-center justify-center">
        <FileDropzone multiple />
      </CardContent>
    </Card>
  )
}
