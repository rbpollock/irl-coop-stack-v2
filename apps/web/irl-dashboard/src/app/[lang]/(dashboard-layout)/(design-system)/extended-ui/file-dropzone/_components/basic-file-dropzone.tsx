import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { FileDropzone } from "@/components/ui/file-dropzone"

export function BasicFileDropzone() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Basic File Dropzone</CardTitle>
      </CardHeader>
      <CardContent className="flex items-center justify-center">
        <FileDropzone />
      </CardContent>
    </Card>
  )
}
