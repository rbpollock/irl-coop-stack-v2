import type { CustomerSatisfactionType } from "../types"

export const customerSatisfactionData: CustomerSatisfactionType = {
  period: "Last week",
  summary: {
    name: "Total rating",
    value: 3.8,
  },
  feedbacks: [
    {
      name: "Emily Smith",
      email: "emily.smith@example.com",
      avatar: "/images/avatars/female-01.svg",
      rating: 4.5,
      feedbackMessage: "Great service! Everything was handled smoothly.",
      createdAt: new Date("2024-11-20T14:35:00Z"),
    },
    {
      name: "Michael Brown",
      email: "michael.brown@example.com",
      avatar: "/images/avatars/male-02.svg",
      rating: 3.0,
      feedbackMessage:
        "The experience was decent overall, but there is definitely room for improvement. Some aspects of the service felt rushed, and communication could have been clearer. I hope future interactions are smoother.",
      createdAt: new Date("2024-11-19T10:15:00Z"),
    },
    {
      name: "Olivia Martinez",
      email: "olivia.martinez@example.com",
      avatar: "/images/avatars/female-03.svg",
      rating: 5.0,
      feedbackMessage: "Exceptional service!",
      createdAt: new Date("2024-11-18T09:45:00Z"),
    },
    {
      name: "John Doe",
      email: "john.doe@example.com",
      avatar: "/images/avatars/male-01.svg",
      rating: 2.5,
      feedbackMessage:
        "Unfortunately, I faced several issues with the product delivery, which impacted my overall experience. The delays were frustrating, and I struggled to get proper updates. While there were some positives, these challenges made the experience less than ideal.",
      createdAt: new Date("2024-11-17T17:00:00Z"),
    },
    {
      name: "Sarah Johnson",
      email: "sarah.johnson@example.com",
      avatar: "/images/avatars/female-02.svg",
      rating: 4.0,
      feedbackMessage:
        "I had a good experience overall. The team was friendly and efficient, and I felt that they genuinely cared about my satisfaction. There’s always room for small improvements, but I’d definitely recommend them to others looking for reliable service.",
      createdAt: new Date("2024-11-16T12:30:00Z"),
    },
  ],
}
