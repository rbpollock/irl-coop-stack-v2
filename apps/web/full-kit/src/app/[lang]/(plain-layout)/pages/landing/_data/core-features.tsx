import Image from "next/image"
import {
  Code,
  Globe,
  Languages,
  MonitorSmartphone,
  PencilRuler,
  SunMoon,
} from "lucide-react"

import type { CoreFeatureType } from "../types"

import { BentoHeader } from "@/components/ui/bento-grid"
import { Card } from "@/components/ui/card"
import { Iphone15Pro } from "@/components/ui/iphone-15-pro"

export const coreFeaturesData: CoreFeatureType[] = [
  {
    title: "Clean Code & Well-Documented",
    description:
      "Developer-friendly structure with clear documentation, starter guides, and maintainable, readable code.",
    icon: Code,
    className: "md:[&>div]:first:basis-1/3 md:col-span-2 md:flex-row",
    header: (
      <BentoHeader className="hidden md:block">
        <Card>
          <Image
            src="/images/illustrations/misc/whiteboard.svg"
            alt=""
            height={1080}
            width={1080}
            className="h-56 w-full object-cover bg-white overflow-hidden dark:invert"
          />
        </Card>
      </BentoHeader>
    ),
  },
  {
    title: "Responsive & Modern Design",
    description:
      "Sleek, adaptive layouts that look great on all devices and screen sizes.",
    icon: MonitorSmartphone,
    className: "md:row-span-3 md:pb-0",
    header: (
      <BentoHeader className="hidden max-h-114 overflow-hidden md:block">
        <Iphone15Pro
          imageSrc="/images/misc/mobile.jpg"
          className="h-auto w-full dark:hidden"
          id="iphone-15-pro-1"
        />
        <Iphone15Pro
          imageSrc="/images/misc/mobile-dark.jpg"
          className="hidden h-auto w-full dark:md:block"
          id="iphone-15-pro-2"
        />
      </BentoHeader>
    ),
  },
  {
    title: "Fully Customizable",
    description:
      "Tweak colors, typography, and layouts with ease to match your brand or project needs.",
    icon: PencilRuler,
    className: "",
  },
  {
    title: "Dark & Light Modes",
    description:
      "Built-in theme switcher with dark, light, and transparent modes to match user preferences.",
    icon: SunMoon,
    className: "",
  },
  {
    title: "RTL & Multilingual Ready",
    description:
      "Supports right-to-left languages and internationalization for global reach.",
    icon: Languages,
  },
  {
    title: "Cross-Browser & Accessibility Ready",
    description:
      "Consistent performance across all major browsers with built-in accessibility support.",
    icon: Globe,
  },
]
