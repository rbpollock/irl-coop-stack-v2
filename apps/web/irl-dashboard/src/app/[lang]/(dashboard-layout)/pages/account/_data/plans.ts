import type { PlanType } from "../types"

export const plansData: PlanType[] = [
  {
    id: 1,
    name: "Starter",
    price: 9.99,
    features: [
      "Up to 5 active projects",
      "Up to 10 team members",
      "20 GB storage",
      "Basic project analytics",
      "Email support",
    ],
  },
  {
    id: 2,
    name: "Business",
    price: 19.99,
    features: [
      "Up to 20 active projects",
      "Up to 25 team members",
      "100 GB storage",
      "Advanced project analytics",
      "Custom workflows",
      "Priority support",
      "API access",
    ],
  },
  {
    id: 3,
    name: "Enterprise",
    price: 199.99,
    features: [
      "Unlimited active projects",
      "Unlimited team members",
      "Unlimited storage",
      "Advanced project analytics",
      "Custom workflows",
      "Dedicated support",
      "API access",
      "Custom integrations",
      "On-premise deployment option",
    ],
  },
]
