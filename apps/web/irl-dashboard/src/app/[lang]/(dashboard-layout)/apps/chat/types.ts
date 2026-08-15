import type { FileType } from "@/types"
import type { z } from "zod"
import type { FilesUploaderSchema } from "./_schemas/files-uploader-schema"
import type { ImagesUploaderSchema } from "./_schemas/images-uploader-schema"
import type { TextMessageSchema } from "./_schemas/text-message-schema"

export interface ChatContextType {
  chatState: ChatStateType
  isChatSidebarOpen: boolean
  setIsChatSidebarOpen: (val: boolean) => void
  handleSelectChat: (chat: ChatType) => void
  handleAddTextMessage: (text: string) => void
  handleAddImagesMessage: (images: FileType[]) => void
  handleAddFilesMessage: (files: FileType[]) => void
  handleSetUnreadCount: () => void
}

export type ChatStatusType = "READ" | "DELIVERED" | "SENT" | null

export interface MessageType {
  id: string
  senderId: string
  text?: string
  images?: FileType[]
  files?: FileType[]
  voiceMessage?: FileType
  status: string
  createdAt: Date
}

export type NewMessageType = Omit<
  MessageType,
  "id" | "senderId" | "createdAt" | "images" | "files" | "voiceMessage"
> & {
  images?: FileType[]
  files?: FileType[]
  voiceMessage?: FileType
}

export interface UserType {
  id: string
  name: string
  avatar?: string
  status: string
}

export interface LastMessageType {
  content: string
  createdAt: Date
}

export interface ChatType {
  id: string
  lastMessage: LastMessageType
  name: string
  avatar?: string
  status?: string
  messages: MessageType[]
  users: UserType[]
  typingUsers: UserType[]
  unreadCount?: number
}

export interface ChatStateType {
  chats: ChatType[]
  selectedChat?: ChatType | null
}

export type ChatActionType =
  | {
      type: "addTextMessage"
      text: string
    }
  | {
      type: "addImagesMessage"
      images: FileType[]
    }
  | {
      type: "addFilesMessage"
      files: FileType[]
    }
  | {
      type: "setUnreadCount"
    }
  | {
      type: "selectChat"
      chat: ChatType
    }

export type TextMessageFormType = z.infer<typeof TextMessageSchema>

export type FilesUploaderFormType = z.infer<typeof FilesUploaderSchema>

export type ImagesUploaderFormType = z.infer<typeof ImagesUploaderSchema>
