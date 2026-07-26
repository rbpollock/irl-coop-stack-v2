"use client"

import { createContext, useCallback, useReducer, useState } from "react"

import type { ReactNode } from "react"
import type {
  EmailContextType,
  EmailSidebarItemsType,
  EmailType,
} from "../types"

import { EmailReducer } from "../_reducers/email-reducer"

// Create Email context
export const EmailContext = createContext<EmailContextType | undefined>(
  undefined
)

export function EmailProvider({
  emailsData,
  sidebarItemsData,
  children,
}: {
  emailsData: EmailType[]
  sidebarItemsData: EmailSidebarItemsType
  children: ReactNode
}) {
  // Reducer to manage Email state
  const [emailState, dispatch] = useReducer(EmailReducer, {
    initialEmails: emailsData,
    sidebarItems: sidebarItemsData,
    emails: [],
    selectedEmails: [],
    currentPage: 1,
    totalPages: 1,
    totalEmails: 0,
  })

  // Sidebar state management
  const [isEmailSidebarOpen, setIsEmailSidebarOpen] = useState(false)

  // Handlers for email actions
  const handleGetFilteredEmails = useCallback(
    (filter: string, currentPage: number) => {
      dispatch({ type: "getFilteredEmails", filter, currentPage })
    },
    []
  )

  const handleGetFilteredEmailsBySearchTerm = useCallback(
    (term: string, filter: string, currentPage: number) => {
      dispatch({
        type: "getFilteredEmailsBySearchTerm",
        term,
        filter,
        currentPage,
      })
    },
    []
  )

  function handleToggleSelectEmail(email: EmailType) {
    dispatch({
      type: "toggleSelectEmail",
      email,
    })
  }

  function handleToggleSelectAllEmails() {
    dispatch({
      type: "toggleSelectAllEmail",
    })
  }

  function handleToggleStarEmail(email: EmailType) {
    dispatch({
      type: "toggleStarEmail",
      email,
    })
  }

  function handleSetRead(email: EmailType) {
    dispatch({
      type: "setRead",
      email,
    })
  }

  return (
    <EmailContext.Provider
      value={{
        emailState,
        handleGetFilteredEmails,
        handleGetFilteredEmailsBySearchTerm,
        handleToggleSelectEmail,
        handleToggleSelectAllEmails,
        handleToggleStarEmail,
        isEmailSidebarOpen,
        setIsEmailSidebarOpen,
        handleSetRead,
      }}
    >
      {children}
    </EmailContext.Provider>
  )
}
