import type { SubscriptionType } from "../types"

export const subscriptionsData: SubscriptionType[] = [
  {
    id: 1,
    planId: 1,
    interval: "monthly",
    startDate: "2024-09-01T10:30:00.000Z",
    endDate: "2024-10-01T10:30:00.000Z",
    status: "active",
  },
  {
    id: 2,
    planId: 2,
    interval: "monthly",
    startDate: "2024-09-02T11:00:00.000Z",
    endDate: "2024-10-02T11:00:00.000Z",
    status: "active",
    createdAt: "2024-09-02T11:00:00.000Z",
    updatedAt: "2024-09-02T11:00:00.000Z",
  },
  {
    id: 3,
    planId: 3,
    interval: "monthly",
    startDate: "2023-09-01T11:30:00.000Z",
    endDate: "2024-09-01T11:30:00.000Z",
    status: "expired",
    createdAt: "2023-09-01T11:30:00.000Z",
    updatedAt: "2024-09-01T11:30:00.000Z",
  },
]
