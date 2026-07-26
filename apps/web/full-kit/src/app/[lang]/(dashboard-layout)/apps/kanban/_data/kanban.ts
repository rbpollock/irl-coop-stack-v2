import type { ColumnType } from "../types"

export const kanbanData: ColumnType[] = [
  {
    id: "backlog",
    title: "Backlog",
    order: 0,
    tasks: [
      {
        id: "task-0",
        columnId: "backlog",
        order: 0,
        title: "Research Project",
        description: "Conduct initial research on market trends.",
        label: "Research",
        assigned: [
          {
            id: "member-0",
            username: "john.doe",
            name: "John Doe",
            avatar: "/images/avatars/male-01.svg",
          },
          {
            id: "member-1",
            username: "emily.smith",
            name: "Emily Smith",
            avatar: "/images/avatars/female-01.svg",
          },
          {
            id: "member-2",
            username: "michael.brown",
            name: "Michael Brown",
            avatar: "/images/avatars/male-02.svg",
          },
          {
            id: "member-3",
            username: "sarah.johnson",
            name: "Sarah Johnson",
            avatar: "/images/avatars/female-02.svg",
          },
          {
            id: "member-4",
            username: "olivia.martinez",
            name: "Olivia Martinez",
            avatar: "/images/avatars/female-03.svg",
          },
        ],
        dueDate: new Date(),
        attachments: [
          {
            id: "attachment-0",
            url: "/research-report.pdf",
            name: "research-report.pdf",
            size: 1048576,
            type: "application/pdf",
          },
          {
            id: "attachment-1",
            url: "/images/illustrations/scenes/scene-02.svg",
            name: "scene-02.svg",
            size: 524288,
            type: "image/jpeg",
          },
        ],
        comments: [
          {
            id: "comment-0",
            userId: "member-0",
            text: "Let's start gathering data.",
            createdAt: new Date(),
          },
        ],
      },
      {
        id: "task-1",
        columnId: "backlog",
        order: 1,
        title: "Design Wireframe",
        description: "Create a wireframe for the new feature.",
        label: "Design",
        assigned: [
          {
            id: "member-0",
            username: "john.doe",
            name: "John Doe",
            avatar: "/images/avatars/male-01.svg",
          },
          {
            id: "member-1",
            username: "emily.smith",
            name: "Emily Smith",
            avatar: "/images/avatars/female-01.svg",
          },
          {
            id: "member-2",
            username: "michael.brown",
            name: "Michael Brown",
            avatar: "/images/avatars/male-02.svg",
          },
          {
            id: "member-4",
            username: "sarah.johnson",
            name: "Sarah Johnson",
            avatar: "/images/avatars/female-02.svg",
          },
        ],
        dueDate: new Date(),
        attachments: [],
        comments: [
          {
            id: "comment-1",
            userId: "member-0",
            text: "We need to focus on user experience.",
            createdAt: new Date(),
          },
          {
            id: "comment-2",
            userId: "member-2",
            text: "Can we add more options for users?",
            createdAt: new Date(),
          },
        ],
      },
    ],
  },
  {
    id: "in-progress",
    title: "In Progress",
    order: 1,
    tasks: [
      {
        id: "task-3",
        columnId: "in-progress",
        order: 0,
        title: "Develop API",
        description: "Build the API for user authentication.",
        label: "Development",
        assigned: [
          {
            id: "member-2",
            username: "olivia.martinez",
            name: "Olivia Martinez",
            avatar: "/images/avatars/female-03.svg",
          },
          {
            id: "member-3",
            username: "olivia.clark",
            name: "Olivia Clark",
            avatar: "/images/avatars/female-01.svg",
          },
        ],
        dueDate: new Date(),
        attachments: [
          {
            id: "attachment-2",
            url: "/images/illustrations/scenes/scene-01.svg",
            name: "scene-01.svg",
            size: 524288,
            type: "image/jpeg",
          },
          {
            id: "attachment-3",
            url: "/images/illustrations/scenes/scene-02.svg",
            name: "scene-02.svg",
            size: 524288,
            type: "image/jpeg",
          },
          {
            id: "attachment-4",
            url: "/images/illustrations/scenes/scene-03.svg",
            name: "scene-03.svg",
            size: 524288,
            type: "image/jpeg",
          },
          {
            id: "attachment-5",
            url: "/images/illustrations/scenes/scene-04.svg",
            name: "scene-04.svg",
            size: 524288,
            type: "image/jpeg",
          },
          {
            id: "attachment-6",
            url: "/images/illustrations/scenes/scene-04.svg",
            name: "scene-05.svg",
            size: 524288,
            type: "image/jpeg",
          },
          {
            id: "attachment-7",
            url: "/api-specs.pdf",
            name: "api-specs.pdf",
            size: 2097152,
            type: "application/pdf",
          },
        ],
        comments: [
          {
            id: "comment-3",
            userId: "member-2",
            text: "I started on the endpoints.",
            createdAt: new Date(),
          },
          {
            id: "comment-4",
            userId: "member-3",
            text: "Let me know if you need help!",
            createdAt: new Date(),
          },
        ],
      },
      {
        id: "task-4",
        columnId: "in-progress",
        order: 1,
        title: "Update UI",
        description: "Revise the user interface for better UX.",
        label: "Design",
        assigned: [
          {
            id: "member-0",
            username: "john.doe",
            name: "John Doe",
            avatar: "/images/avatars/male-01.svg",
          },
        ],
        dueDate: new Date(),
        attachments: [],
        comments: [
          {
            id: "comment-5",
            userId: "member-0",
            text: "What do you think about the new color scheme?",
            createdAt: new Date(),
          },
        ],
      },
    ],
  },
  {
    id: "done",
    title: "Done",
    order: 2,
    tasks: [
      {
        id: "task-5",
        columnId: "done",
        order: 0,
        title: "Write Documentation",
        description: "Prepare the project documentation for release.",
        label: "Documentation",
        assigned: [
          {
            id: "member-2",
            username: "michael.brown",
            name: "Michael Brown",
            avatar: "/images/avatars/male-02.svg",
          },
          {
            id: "member-3",
            username: "sarah.johnson",
            name: "Sarah Johnson",
            avatar: "/images/avatars/female-02.svg",
          },
          {
            id: "member-4",
            username: "olivia.martinez",
            name: "Olivia Martinez",
            avatar: "/images/avatars/female-03.svg",
          },
        ],
        dueDate: new Date(),
        attachments: [
          {
            id: "attachment-8",
            url: "/project-docs.pdf",
            name: "project-docs.pdf",
            size: 1572864,
            type: "application/pdf",
          },
        ],
        comments: [
          {
            id: "comment-6",
            userId: "member-2",
            text: "Documentation is complete!",
            createdAt: new Date(),
          },
          {
            id: "comment-7",
            userId: "member-3",
            text: "Looks good, ready for review.",
            createdAt: new Date(),
          },
        ],
      },
      {
        id: "task-6",
        columnId: "done",
        order: 1,
        title: "Fix Bugs",
        description: "Resolve all known bugs from the previous release.",
        label: "QA",
        assigned: [
          {
            id: "member-0",
            username: "john.doe",
            name: "John Doe",
            avatar: "/images/avatars/male-01.svg",
          },
          {
            id: "member-1",
            username: "emily.smith",
            name: "Emily Smith",
            avatar: "/images/avatars/female-01.svg",
          },
          {
            id: "member-2",
            username: "michael.brown",
            name: "Michael Brown",
            avatar: "/images/avatars/male-02.svg",
          },
          {
            id: "member-3",
            username: "sarah.johnson",
            name: "Sarah Johnson",
            avatar: "/images/avatars/female-02.svg",
          },
        ],
        dueDate: new Date(),
        attachments: [
          {
            id: "attachment-9",
            url: "/bug-report.pdf",
            name: "bug-report.pdf",
            size: 512000,
            type: "application/pdf",
          },
        ],
        comments: [
          {
            id: "comment-8",
            userId: "member-1",
            text: "All bugs have been fixed.",
            createdAt: new Date(),
          },
          {
            id: "comment-9",
            userId: "member-0",
            text: "Great teamwork!",
            createdAt: new Date(),
          },
        ],
      },
      {
        id: "task-7",
        columnId: "done",
        order: 2,
        title: "Launch Campaign",
        description: "Officially launch the marketing campaign.",
        label: "Marketing",
        assigned: [
          {
            id: "member-1",
            username: "emily.smith",
            name: "Emily Smith",
            avatar: "/images/avatars/female-01.svg",
          },
          {
            id: "member-2",
            username: "michael.brown",
            name: "Michael Brown",
            avatar: "/images/avatars/male-02.svg",
          },
          {
            id: "member-0",
            username: "john.doe",
            name: "John Doe",
            avatar: "/images/avatars/male-01.svg",
          },
        ],
        dueDate: new Date(),
        attachments: [
          {
            id: "attachment-10",
            url: "/campaign-plan.pdf",
            name: "Campaign Plan",
            size: 1310720,
            type: "application/pdf",
          },
        ],
        comments: [
          {
            id: "comment-10",
            userId: "member-1",
            text: "The campaign is live!",
            createdAt: new Date(),
          },
          {
            id: "comment-11",
            userId: "member-2",
            text: "Let’s monitor the response closely.",
            createdAt: new Date(),
          },
        ],
      },
    ],
  },
]
