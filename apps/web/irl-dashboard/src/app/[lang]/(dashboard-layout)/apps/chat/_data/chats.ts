import type { ChatType } from "../types"

export const chatsData: ChatType[] = [
  {
    id: "chat_1",
    lastMessage: {
      content: "Thank you for the update. I'll review it shortly.",
      createdAt: new Date("2024-10-31T10:37:00Z"),
    },
    name: "Tech Team Discussions",
    messages: [
      {
        id: "msg_24",
        senderId: "1",
        text: "Thank you for the update. I'll review it shortly.",
        createdAt: new Date("2024-10-31T10:37:00Z"),
        status: "DELIVERED",
      },
      {
        id: "msg_23",
        senderId: "5",
        files: [
          {
            id: "file_1",
            name: "Flowchart_Updated.pdf",
            type: "application/pdf",
            size: 204800,
            url: "",
          },
        ],
        createdAt: new Date("2024-10-31T10:34:00Z"),
        status: "READ",
      },
      {
        id: "msg_22",
        senderId: "5",
        text: "Here's the updated flowchart for review.",
        files: [
          {
            id: "file_1",
            name: "flowchart-updated",
            type: "application/pdf",
            size: 204800,
            url: "",
          },
        ],
        createdAt: new Date("2024-10-31T10:33:00Z"),
        status: "READ",
      },
      {
        id: "msg_21",
        senderId: "1",
        text: "Looks good! Do we have an alternative version?",
        createdAt: new Date("2024-10-31T10:10:00Z"),
        status: "READ",
      },
      {
        id: "msg_20",
        senderId: "5",
        text: "This mockup might help visualize the design.",
        createdAt: new Date("2024-10-31T10:08:00Z"),
        status: "READ",
      },
      {
        id: "msg_19",
        senderId: "5",
        images: [
          {
            id: "img_1",
            name: "mockup-home-page",
            type: "image/svg",
            size: 512000,
            url: "/images/illustrations/misc/whiteboard.svg",
          },
        ],
        createdAt: new Date("2024-10-31T10:07:00Z"),
        status: "READ",
      },
    ],
    users: [
      {
        id: "1",
        name: "John Doe",
        avatar: "/images/avatars/male-01.svg",
        status: "ONLINE",
      },
      {
        id: "5",
        name: "Sarah Johnson",
        avatar: "/images/avatars/female-02.svg",
        status: "ONLINE",
      },
    ],
    typingUsers: [],
  },
  {
    id: "chat_2",
    lastMessage: {
      content: "Hello everyone!",
      createdAt: new Date("2024-10-31T10:03:00Z"),
    },
    name: "General Group",
    messages: [
      {
        id: "msg_12",
        senderId: "2",
        text: "Pretty good! Just getting started with the day.",
        createdAt: new Date("2024-10-31T10:03:00Z"),
        status: "DELIVERED",
      },
      {
        id: "msg_11",
        senderId: "1",
        text: "How's everyone doing today?",
        createdAt: new Date("2024-10-31T10:02:00Z"),
        status: "READ",
      },
      {
        id: "msg_2",
        senderId: "1",
        text: "Hey Olivia!",
        createdAt: new Date("2024-10-31T10:01:00Z"),
        status: "READ",
      },
      {
        id: "msg_1",
        senderId: "2",
        text: "Hello everyone!",
        createdAt: new Date("2024-10-31T10:00:00Z"),
        status: "READ",
      },
    ],
    users: [
      {
        id: "1",
        name: "John Doe",
        avatar: "/images/avatars/male-01.svg",
        status: "ONLINE",
      },
      {
        id: "2",
        name: "Olivia Martinez",
        avatar: "/images/avatars/female-03.svg",
        status: "IDLE",
      },
    ],
    typingUsers: [],
    unreadCount: 1,
  },
  {
    id: "chat_3",
    lastMessage: {
      content: "Hey, did you see the updates?",
      createdAt: new Date("2024-10-31T10:08:00Z"),
    },
    name: "Olivia Martinez",
    avatar: "/images/avatars/female-03.svg",
    status: "IDLE",
    messages: [
      {
        id: "msg_14",
        senderId: "1",
        text: "Great! Let's keep it that way.",
        createdAt: new Date("2024-10-31T10:08:00Z"),
        status: "READ",
      },
      {
        id: "msg_13",
        senderId: "2",
        text: "They look good! I think we're on track.",
        createdAt: new Date("2024-10-31T10:07:00Z"),
        status: "READ",
      },
      {
        id: "msg_4",
        senderId: "1",
        text: "Yes, I checked them this morning.",
        createdAt: new Date("2024-10-31T10:06:00Z"),
        status: "READ",
      },
      {
        id: "msg_3",
        senderId: "2",
        text: "Hey, did you see the updates?",
        createdAt: new Date("2024-10-31T10:05:00Z"),
        status: "READ",
      },
    ],
    users: [
      {
        id: "1",
        name: "John Doe",
        avatar: "/images/avatars/male-01.svg",
        status: "ONLINE",
      },
      {
        id: "2",
        name: "Olivia Martinez",
        avatar: "/images/avatars/female-03.svg",
        status: "IDLE",
      },
    ],
    typingUsers: [],
  },
  {
    id: "chat_4",
    lastMessage: {
      content: "Meeting at 3 PM tomorrow.",
      createdAt: new Date("2024-10-31T10:13:00Z"),
    },
    name: "Work Team",
    messages: [
      {
        id: "msg_16",
        senderId: "4",
        text: "Sure! I'll prepare that.",
        createdAt: new Date("2024-10-31T10:13:00Z"),
        status: "READ",
      },
      {
        id: "msg_15",
        senderId: "3",
        text: "Can you send out the agenda before then?",
        createdAt: new Date("2024-10-31T10:12:00Z"),
        status: "READ",
      },
      {
        id: "msg_6",
        senderId: "4",
        text: "Got it! I'll be there.",
        createdAt: new Date("2024-10-31T10:11:00Z"),
        status: "READ",
      },
      {
        id: "msg_5",
        senderId: "3",
        text: "Meeting at 3 PM tomorrow.",
        createdAt: new Date("2024-10-31T10:10:00Z"),
        status: "READ",
      },
    ],
    users: [
      {
        id: "3",
        name: "Michael Brown",
        avatar: "/images/avatars/male-02.svg",
        status: "ONLINE",
      },
      {
        id: "4",
        name: "Emily Smith",
        avatar: "/images/avatars/female-01.svg",
        status: "DO NOT DISTURB",
      },
    ],
    typingUsers: [],
  },
  {
    id: "chat_5",
    lastMessage: {
      content: "Let’s grab lunch later?",
      createdAt: new Date("2024-10-31T10:18:00Z"),
    },
    name: "Michael Johnson",
    avatar: "/images/avatars/male-02.svg",
    status: "ONLINE",
    messages: [
      {
        id: "msg_18",
        senderId: "3",
        text: "Sounds good! I'll see you then.",
        createdAt: new Date("2024-10-31T10:18:00Z"),
        status: "READ",
      },
      {
        id: "msg_17",
        senderId: "1",
        text: "How about 1 PM?",
        createdAt: new Date("2024-10-31T10:17:00Z"),
        status: "READ",
      },
      {
        id: "msg_8",
        senderId: "3",
        text: "Sure! What time?",
        createdAt: new Date("2024-10-31T10:16:00Z"),
        status: "READ",
      },
      {
        id: "msg_7",
        senderId: "1",
        text: "Let’s grab lunch later?",
        createdAt: new Date("2024-10-31T10:15:00Z"),
        status: "READ",
      },
    ],
    users: [
      {
        id: "1",
        name: "John Doe",
        avatar: "/images/avatars/male-01.svg",
        status: "ONLINE",
      },
      {
        id: "3",
        name: "Michael Johnson",
        avatar: "/images/avatars/male-02.svg",
        status: "ONLINE",
      },
    ],
    typingUsers: [],
  },
]
