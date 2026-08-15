import type { Metadata } from "next"

import { BasicFileDropzone } from "../../extended-ui/file-dropzone/_components/basic-file-dropzone"
import { FileDropzoneMaxFiles } from "../../extended-ui/file-dropzone/_components/file-dropzone-max-files"
import { FileDropzoneMaxSize } from "../../extended-ui/file-dropzone/_components/file-dropzone-max-size"
import { FileDropzoneMultiple } from "../../extended-ui/file-dropzone/_components/file-dropzone-multiple"

// Define metadata for the page
// More info: https://nextjs.org/docs/app/building-your-application/optimizing/metadata
export const metadata: Metadata = {
  title: "File Dropzones",
}

export default function FileDropzonesPage() {
  return (
    <section className="container grid gap-4 p-4 md:grid-cols-2">
      <BasicFileDropzone />
      <FileDropzoneMultiple />
      <FileDropzoneMaxFiles />
      <FileDropzoneMaxSize />
    </section>
  )
}
