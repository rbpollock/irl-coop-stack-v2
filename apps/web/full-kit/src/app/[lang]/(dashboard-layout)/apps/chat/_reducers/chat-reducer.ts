"use client"

import type { ChatActionType, ChatStateType, MessageType } from "../types"

export const ChatReducer = (
  state: ChatStateType,
  action: ChatActionType
): ChatStateType => {
  switch (action.type) {
    case "addTextMessage": {
      if (!state.selectedChat) {
        return state // No selected chat, return the current state
      }

      const newMessage: MessageType = {
        id: crypto.randomUUID(), // Generate a unique ID for the message
        senderId: "1", // Assuming "1" represents the current user
        text: action.text, // Set the text content
        status: "DELIVERED", // Message delivery status
        createdAt: new Date(), // Set the current timestamp
      }

      const { id, messages } = state.selectedChat

      const updatedChat = {
        ...state.selectedChat,
        lastMessage: {
          content: action.text, // Update the last message content
          createdAt: newMessage.createdAt, // Update the timestamp
        },
        messages: [newMessage, ...messages], // Add the new message to the top
      }

      const updatedChats = state.chats.map(
        (chat) => (chat.id === id ? updatedChat : chat) // Update the relevant chat
      )

      return { ...state, chats: updatedChats }
    }

    case "addImagesMessage": {
      if (!state.selectedChat) {
        return state // No selected chat, return the current state
      }

      const newMessage: MessageType = {
        id: crypto.randomUUID(),
        senderId: "1",
        images: action.images, // Attach the images to the message
        status: "DELIVERED",
        createdAt: new Date(),
      }

      const { id, messages } = state.selectedChat

      const updatedChat = {
        ...state.selectedChat,
        lastMessage: {
          content: action.images.length > 1 ? "Images" : "Image", // Update the last message to reflect images
          createdAt: newMessage.createdAt,
        },
        messages: [newMessage, ...messages], // Add the new message
      }

      const updatedChats = state.chats.map(
        (chat) => (chat.id === id ? updatedChat : chat) // Update the relevant chat
      )

      return { ...state, chats: updatedChats }
    }

    case "addFilesMessage": {
      if (!state.selectedChat) {
        return state // No selected chat, return the current state
      }

      const newMessage: MessageType = {
        id: crypto.randomUUID(),
        senderId: "1",
        files: action.files, // Attach the files to the message
        status: "DELIVERED",
        createdAt: new Date(),
      }

      const { id, messages } = state.selectedChat

      const updatedChat = {
        ...state.selectedChat,
        lastMessage: {
          content: action.files.length > 1 ? "Files" : "File", // Update the last message to reflect files
          createdAt: newMessage.createdAt,
        },
        messages: [newMessage, ...messages], // Add the new message
      }

      const updatedChats = state.chats.map(
        (chat) => (chat.id === id ? updatedChat : chat) // Update the relevant chat
      )

      return { ...state, chats: updatedChats }
    }

    case "setUnreadCount": {
      if (!state.selectedChat) {
        return state // No selected chat, return the current state
      }

      const { id } = state.selectedChat

      const updatedChat = {
        ...state.selectedChat,
        unreadCount: 0, // Reset unread count for the selected chat
      }

      const updatedChats = state.chats.map(
        (chat) => (chat.id === id ? updatedChat : chat) // Update the relevant chat
      )

      return { ...state, chats: updatedChats }
    }

    case "selectChat": {
      return { ...state, selectedChat: action.chat } // Set the selected chat
    }

    default:
      return state // Return the current state for unknown actions
  }
}
