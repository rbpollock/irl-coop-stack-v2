import type { Metadata } from "next"

import { BasicFileDropzone } from "./_components/basic-file-dropzone"
import { FileDropzoneMaxFiles } from "./_components/file-dropzone-max-files"
import { FileDropzoneMaxSize } from "./_components/file-dropzone-max-size"
import { FileDropzoneMultiple } from "./_components/file-dropzone-multiple"

// Define metadata for the page
// More info: https://nextjs.org/docs/app/building-your-application/optimizing/metadata
export const metadata: Metadata = {
  title: "File Dropzone",
}

export default function FileDropzonePage() {
  return (
    <section className="container grid gap-4 p-4 md:grid-cols-2">
      <BasicFileDropzone />
      <FileDropzoneMultiple />
      <FileDropzoneMaxFiles />
      <FileDropzoneMaxSize />
    </section>
  )
}
