declare module "@cubone/react-file-manager" {
  import type { FC, ReactNode } from "react"

  export interface FileManagerFile {
    name: string
    isDirectory: boolean
    path: string
    updatedAt?: string
    size?: number
  }

  export interface FileUploadConfig {
    url: string
    method?: "POST" | "PUT"
    headers?: Record<string, string>
    withCredentials?: boolean
  }

  export interface FileManagerProps {
    files: FileManagerFile[]
    acceptedFileTypes?: string
    className?: string
    collapsibleNav?: boolean
    defaultNavExpanded?: boolean
    enableFilePreview?: boolean
    filePreviewPath?: string
    filePreviewComponent?: (file: FileManagerFile) => ReactNode
    fileUploadConfig?: FileUploadConfig
    fontFamily?: string
    height?: string | number
    initialPath?: string
    isLoading?: boolean
    language?: string
    layout?: "list" | "grid"
    maxFileSize?: number
    onCopy?: (files: FileManagerFile[]) => void
    onCut?: (files: FileManagerFile[]) => void
    onCreateFolder?: (name: string, parentFolder: FileManagerFile) => void
    onDelete?: (files: FileManagerFile[]) => void
    onDownload?: (files: FileManagerFile[]) => void
    onError?: (
      error: { type: string; message: string },
      file: FileManagerFile,
    ) => void
    onFileOpen?: (file: FileManagerFile) => void
    onFileUploaded?: (response: Record<string, unknown>) => void
    onFileUploading?: (
      file: FileManagerFile,
      parentFolder: FileManagerFile,
    ) => Record<string, unknown>
    onFolderChange?: (path: string) => void
    onLayoutChange?: (layout: "list" | "grid") => void
    onPaste?: (
      files: FileManagerFile[],
      destinationFolder: FileManagerFile,
      operationType: "copy" | "move",
    ) => void
    onRefresh?: () => void
    onRename?: (file: FileManagerFile, newName: string) => void
    onSelectionChange?: (files: FileManagerFile[]) => void
    onSortChange?: (sortConfig: {
      key: "name" | "modified" | "size"
      direction: "asc" | "desc"
    }) => void
    permissions?: {
      create?: boolean
      upload?: boolean
      move?: boolean
      copy?: boolean
      rename?: boolean
      download?: boolean
      delete?: boolean
    }
    primaryColor?: string
    style?: object
    width?: string | number
  }

  export const FileManager: FC<FileManagerProps>
}
