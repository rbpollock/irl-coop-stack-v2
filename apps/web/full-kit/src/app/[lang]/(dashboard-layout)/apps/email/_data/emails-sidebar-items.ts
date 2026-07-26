import type { EmailSidebarItemsType } from "../types"

export const sidebarItemsData: EmailSidebarItemsType = {
  folders: [
    { iconName: "Archive", name: "inbox", unreadCount: 8 },
    { iconName: "Send", name: "sent", unreadCount: 3 },
    { iconName: "Pencil", name: "draft", unreadCount: 3 },
    { iconName: "Star", name: "starred", unreadCount: 6 },
    { iconName: "Clock", name: "spam", unreadCount: 3 },
    { iconName: "Trash2", name: "trash", unreadCount: 0 },
  ],
  labels: [
    { iconName: "Tag", name: "personal", unreadCount: 1 },
    { iconName: "Tag", name: "work", unreadCount: 11 },
    { iconName: "Tag", name: "important", unreadCount: 3 },
  ],
}
