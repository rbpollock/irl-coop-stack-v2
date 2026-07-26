import type { ActivityTimelineType } from "../types"

export const activityTimelineData: ActivityTimelineType = {
  period: "Today",
  activities: [
    {
      type: "email",
      iconName: "Mail",
      fill: "hsl(var(--chart-1))",
      title: "Follow-up Email to John Doe",
      description:
        "Followed up on the proposal sent last week. Awaiting response.",
      status: "Opened",
      date: "2025-02-27T10:30:00Z",
      assignedMembers: [
        {
          name: "Emily Smith",
          avatar: "/images/avatars/female-01.svg",
          href: "/",
        },
        {
          name: "Michael Brown",
          avatar: "/images/avatars/male-02.svg",
          href: "/",
        },
      ],
    },
    {
      type: "supportTicket",
      iconName: "TicketCheck",
      fill: "hsl(var(--chart-2))",
      title: "Billing Discrepancy Support Ticket",
      description:
        "Ticket ID: TKT-12345 - Customer reported an overcharge, issue resolved with refund processed.",
      status: "Resolved",
      date: "2025-02-27T11:10:00Z",
      assignedMembers: [
        {
          name: "Emily Smith",
          avatar: "/images/avatars/female-01.svg",
          href: "/",
        },
      ],
    },
    {
      type: "dealUpdate",
      iconName: "DollarSign",
      fill: "hsl(var(--chart-3))",
      title: "Enterprise Subscription Deal - Acme Corp",
      description:
        "Negotiation completed. Deal closed at $50,000 annual value.",
      status: "Closed-Won",
      date: "2025-02-27T14:45:00Z",
      assignedMembers: [
        {
          name: "Sarah Johnson",
          avatar: "/images/avatars/female-02.svg",
          href: "/",
        },
        {
          name: "Michael Brown",
          avatar: "/images/avatars/male-02.svg",
          href: "/",
        },
      ],
    },
    {
      type: "call",
      iconName: "Phone",
      fill: "hsl(var(--chart-4))",
      title: "Client Call with Jane Smith",
      description:
        "15-minute call. Jane showed interest and requested a product demo.",
      date: "2025-02-27T15:00:00Z",
      assignedMembers: [
        {
          name: "Michael Brown",
          avatar: "/images/avatars/male-02.svg",
          href: "/",
        },
      ],
    },
    {
      type: "meeting",
      fill: "hsl(var(--chart-5))",
      iconName: "Users",
      title: "Quarterly Planning Session - Global Tech Team",
      description:
        "Discussion on quarterly goals, key initiatives, and strategic planning.",
      status: "Completed",
      date: "2025-02-24T13:00:00Z",
      assignedMembers: [
        {
          name: "John Doe",
          avatar: "/images/avatars/male-01.svg",
          href: "/",
        },
        {
          name: "Michael Brown",
          avatar: "/images/avatars/male-02.svg",
          href: "/",
        },
        {
          name: "Sarah Johnson",
          avatar: "/images/avatars/female-02.svg",
          href: "/",
        },
        {
          name: "Olivia Martinez",
          avatar: "/images/avatars/female-03.svg",
          href: "/",
        },
        {
          name: "Emily Smith",
          avatar: "/images/avatars/female-01.svg",
          href: "/",
        },
      ],
    },
    {
      type: "note",
      iconName: "FileText",
      fill: "hsl(var(--muted-foreground))",
      title: "Internal Note by Alice Thompson",
      description:
        "Client expressed interest in an upsell package. Follow-up recommended next week.",
      date: "2025-02-27T18:20:00Z",
      assignedMembers: [
        {
          name: "John Doe",
          avatar: "/images/avatars/male-01.svg",
          href: "/",
        },
        {
          name: "Emily Smith",
          avatar: "/images/avatars/female-01.svg",
          href: "/",
        },
      ],
    },
  ],
}
