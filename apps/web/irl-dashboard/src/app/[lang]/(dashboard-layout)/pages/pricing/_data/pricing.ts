import type { PricingPlansType } from "@/components/pricing-plans"

export const pricingData: PricingPlansType[] = [
  {
    title: "Starter",
    description:
      "Great for individuals or small teams. Essential features at an affordable price.",
    price: 29.99,
    features: [
      "Manage up to five projects simultaneously",
      "Store and access up to 10 GB of data",
      "Get help with standard support channels",
      "Use essential tools and functionalities",
      "Designed for individual use",
    ],
    isCurrentPlan: true,
    period: "month",
    href: "",
  },
  {
    title: "Company",
    description:
      "Designed for growing teams with enhanced tools and priority support.",
    price: 99.99,
    features: [
      "Handle up to twenty projects at once",
      "Enjoy 50 GB of storage for your data and files",
      "Receive faster response times for support inquiries",
      "Access additional tools and functionalities",
      "Collaborate with up to ten team members",
      "Tailor the dashboard to fit your team’s needs",
    ],
    isFeatured: true,
    period: "month",
    href: "",
  },
  {
    title: "Enterprise",
    description:
      "for large organizations needing full features and dedicated support.",
    price: 299.99,
    features: [
      "Manage an unlimited number of projects",
      "Enjoy ample storage with 200 GB for your data",
      "Get personalized assistance from a dedicated account manager",
      "Access top-tier support with priority and extended hours",
      "No limit on the number of users who can access the plan",
      "Benefit from enhanced security measures and compliance",
      "Integrate with other systems and services as needed",
    ],
    period: "month",
    href: "",
  },
]
