import type { CoreBenefitType } from "../types"

export const coreBenefitsData: CoreBenefitType[] = [
  {
    title: "Empowers Developers to Build Faster",
    description:
      "Shadboard equips developers with the latest tools to rapidly build scalable, modern dashboards with less friction.",
    points: [
      "Modern stack: Next.js 15, React 19, and Tailwind CSS 4",
      "4 ready-made apps and 20+ pages accelerate delivery",
      "Reduces setup time and simplifies component reuse",
    ],
    images: ["/images/illustrations/misc/whiteboard.svg"],
  },
  {
    title: "Designed for Real Teams and Real Users",
    description:
      "With customizable themes and built-in accessibility, Shadboard adapts seamlessly to your team’s needs and user diversity.",
    points: [
      "Shadcn/UI and Radix UI components for a polished, accessible interface",
      "Dark mode, light mode, and full theme customization",
      "Multilingual support (i18n) for global-ready apps",
    ],
    images: ["/images/illustrations/scenes/scene-03.svg"],
  },
  {
    title: "Ready for Real-World Use from Day One",
    description:
      "Shadboard includes essential, production-ready features like authentication, form validation, and rich data components.",
    points: [
      "Secure authentication via NextAuth.js",
      "Smart forms powered by React Hook Form and Zod",
      "Interactive tables and charts with TanStack Table and Recharts",
    ],
    images: ["/images/illustrations/scenes/scene-02.svg"],
  },
]
