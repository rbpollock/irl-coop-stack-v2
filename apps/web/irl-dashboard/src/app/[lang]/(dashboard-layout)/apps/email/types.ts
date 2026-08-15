import type { DynamicIconNameType } from "@/types"
import type { z } from "zod"
import type { EmailComposerSchema } from "./_schemas/email-composer-schema"
import type { EmailListSearchSchema } from "./_schemas/email-list-search-schema"

export interface UserType {
  id: string
  name: string
  avatar?: string
  email: string
  status: string
}

export interface EmailType {
  id: string
  sender: UserType
  subject: string
  content: string
  read: boolean
  starred: boolean
  createdAt: Date
  label?: "personal" | "important" | "work"
  isDraft: boolean
  isSent: boolean
  isStarred: boolean
  isSpam: boolean
  isDeleted: boolean
}

export interface EmailStateType {
  initialEmails: EmailType[]
  sidebarItems: EmailSidebarItemsType
  emails: EmailType[]
  selectedEmails: EmailType[]
  currentPage: number
  totalPages: number
  totalEmails: number
}

export interface EmailSidebarItemType {
  iconName: DynamicIconNameType
  name: string
  unreadCount: number
}

export interface EmailSidebarItemsType {
  folders: Array<EmailSidebarItemType>
  labels: Array<EmailSidebarItemType>
}

export interface EmailContextType {
  emailState: EmailStateType
  isEmailSidebarOpen: boolean
  setIsEmailSidebarOpen: (val: boolean) => void
  handleGetFilteredEmails: (filter: string, currentPage: number) => void
  handleGetFilteredEmailsBySearchTerm: (
    term: string,
    filter: string,
    currentPage: number
  ) => void
  handleToggleSelectEmail: (email: EmailType) => void
  handleToggleSelectAllEmails: () => void
  handleToggleStarEmail: (email: EmailType) => void
  handleSetRead: (email: EmailType) => void
}

export type EmailActionType =
  | {
      type: "getFilteredEmails"
      currentPage: number
      filter: string
    }
  | {
      type: "getFilteredEmailsBySearchTerm"
      currentPage: number
      term: string
      filter: string
    }
  | {
      type: "toggleSelectEmail"
      email: EmailType
    }
  | {
      type: "toggleStarEmail"
      email: EmailType
    }
  | {
      type: "toggleSelectAllEmail"
    }
  | {
      type: "setRead"
      email: EmailType
    }

export type EmailComposerFormType = z.infer<typeof EmailComposerSchema>

export type EmailListSearchFormType = z.infer<typeof EmailListSearchSchema>
