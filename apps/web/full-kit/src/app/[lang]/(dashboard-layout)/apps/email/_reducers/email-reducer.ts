import type { EmailActionType, EmailStateType, EmailType } from "../types"

import { PAGE_SIZE } from "../constants"

function getEmailFolderNames(email: EmailType) {
  const names = new Set()

  if (email.isDeleted) {
    names.add("trash")
  }

  if (email.isSent) {
    names.add("sent")
  }

  if (email.isDraft) {
    names.add("draft")
  }

  if (email.isStarred) {
    names.add("starred")
  }

  if (email.isSpam) {
    names.add("spam")
  }

  if (!email.isSpam && !email.isDeleted && !email.isSent && !email.isDraft) {
    names.add("inbox")
  }

  return names
}

export const EmailReducer = (
  state: EmailStateType,
  action: EmailActionType
): EmailStateType => {
  switch (action.type) {
    case "getFilteredEmails": {
      let filteredEmails = state.initialEmails

      filteredEmails = filteredEmails.filter(
        (email) =>
          getEmailFolderNames(email).has(action.filter) ||
          email.label === action.filter
      )

      // Paginate the filtered emails
      const startIndex = (action.currentPage - 1) * PAGE_SIZE
      const endIndex = startIndex + PAGE_SIZE
      const updatedEmails = filteredEmails.slice(startIndex, endIndex)
      const totalPages = Math.ceil(filteredEmails.length / PAGE_SIZE)
      const totalEmails = filteredEmails.length

      return {
        ...state,
        emails: updatedEmails,
        selectedEmails: [],
        totalPages,
        currentPage: action.currentPage,
        totalEmails,
      }
    }

    case "getFilteredEmailsBySearchTerm": {
      let filteredEmails = state.initialEmails

      filteredEmails = filteredEmails.filter(
        (email) =>
          getEmailFolderNames(email).has(action.filter) ||
          email.label === action.filter
      )

      // Apply term-based search if 'term' is provided
      if (action.term) {
        filteredEmails = filteredEmails.filter(
          (email) =>
            email.subject.toLowerCase().includes(action.term.toLowerCase()) ||
            email.sender.name.toLowerCase().includes(action.term.toLowerCase())
        )
      }

      // Paginate the filtered emails
      const startIndex = (action.currentPage - 1) * PAGE_SIZE
      const endIndex = startIndex + PAGE_SIZE
      const updatedEmails = filteredEmails.slice(startIndex, endIndex)
      const totalPages = Math.ceil(filteredEmails.length / PAGE_SIZE)
      const totalEmails = filteredEmails.length

      return {
        ...state,
        emails: updatedEmails,
        totalPages,
        currentPage: action.currentPage,
        totalEmails,
      }
    }

    case "toggleSelectEmail": {
      const currentSelectedEmails = state.selectedEmails

      const emailIndex = currentSelectedEmails.findIndex(
        (item) => item.id === action.email.id
      )

      let updatedSelectedEmails

      if (emailIndex === -1) {
        // Add the email ID if it is not yet selected
        updatedSelectedEmails = [...currentSelectedEmails, action.email]
      } else {
        // Remove the email ID if it is already selected
        updatedSelectedEmails = currentSelectedEmails.filter(
          ({ id }) => id !== action.email.id
        )
      }

      return {
        ...state,
        selectedEmails: updatedSelectedEmails,
      }
    }

    case "toggleSelectAllEmail": {
      let updatedSelectedEmails: EmailType[]

      if (state.selectedEmails.length === state.emails.length) {
        updatedSelectedEmails = [] // Deselect all if all emails are currently selected
      } else {
        updatedSelectedEmails = state.emails // Select all emails if none or some are selected
      }

      return {
        ...state,
        selectedEmails: updatedSelectedEmails,
      }
    }

    case "toggleStarEmail": {
      const updatedInitalEmails = state.initialEmails.map((email) =>
        email.id === action.email.id
          ? { ...email, starred: !email.starred }
          : email
      )
      const updatedEmails = state.emails.map((email) =>
        email.id === action.email.id
          ? { ...email, starred: !email.starred }
          : email
      )

      let updatedSidebarItems = state.sidebarItems
      if (!action.email.read) {
        const updatedSidebarFolders = state.sidebarItems.folders.map(
          (folder) => {
            if (folder.name == "starred") {
              return {
                ...folder,
                unreadCount: action.email.starred
                  ? folder.unreadCount - 1
                  : folder.unreadCount + 1,
              }
            } else {
              return folder
            }
          }
        )
        updatedSidebarItems = {
          ...state.sidebarItems,
          folders: updatedSidebarFolders,
        }
      }

      return {
        ...state,
        initialEmails: updatedInitalEmails,
        emails: updatedEmails,
        sidebarItems: updatedSidebarItems,
      }
    }

    case "setRead": {
      const updatedEmails = state.emails.map((email) =>
        email.id === action.email.id ? { ...email, read: true } : email
      )
      const updatedInitalEmails = state.initialEmails.map((email) =>
        email.id === action.email.id ? { ...email, read: true } : email
      )

      const folderName = getEmailFolderNames(action.email)
      const updatedSidebarFolders = state.sidebarItems.folders.map((folder) => {
        if (folderName.has(folder.name)) {
          return {
            ...folder,
            unreadCount: folder.unreadCount > 0 ? folder.unreadCount - 1 : 0,
          }
        } else {
          return folder
        }
      })

      const updatedSidebarFLabels = state.sidebarItems.labels.map((label) => {
        if (label.name === action.email.label) {
          return {
            ...label,
            unreadCount: label.unreadCount > 0 ? label.unreadCount - 1 : 0,
          }
        } else {
          return label
        }
      })

      const updatedSidebarItems = {
        folders: updatedSidebarFolders,
        labels: updatedSidebarFLabels,
      }

      return {
        ...state,
        emails: updatedEmails,
        initialEmails: updatedInitalEmails,
        sidebarItems: updatedSidebarItems,
      }
    }

    default:
      return state // Return the current state for unknown actions
  }
}
