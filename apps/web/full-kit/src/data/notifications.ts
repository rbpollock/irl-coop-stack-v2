import type { NotificationType } from "@/types"

export const notificationData: NotificationType = {
  unreadCount: 100,
  notifications: [
    {
      id: "1",
      iconName: "MessageSquare",
      content: "You have a new message from John",
      url: "",
      date: new Date("2024-12-03T10:00:05Z"),
      isRead: false,
    },
    {
      id: "2",
      iconName: "UserPlus",
      content: "John added you as a friend",
      url: "",
      date: new Date("2024-12-03T09:00:00Z"),
      isRead: false,
    },
    {
      id: "3",
      iconName: "ArrowUpRight",
      content: "Check out the new blog post",
      url: "",
      date: new Date("2024-12-02T12:00:00Z"),
      isRead: true,
    },
  ],
}
