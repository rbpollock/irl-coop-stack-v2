import Image from "next/image"
import Link from "next/link"
import { ArrowRight } from "lucide-react"

import { SocialProofBadgeAvatarsData } from "../_data/social-proof-badge-avatars"

import { cn } from "@/lib/utils"

import { AspectRatio } from "@/components/ui/aspect-ratio"
import { AvatarStack } from "@/components/ui/avatar"
import { buttonVariants } from "@/components/ui/button"
import { Card } from "@/components/ui/card"

export function Hero() {
  return (
    <section className="container space-y-10">
      <div className="grid place-items-center text-center gap-y-4">
        <SocialProofBadge />
        <h1 className="text-6xl font-black leading-none">
          Build Smarter, Ship Faster
        </h1>
        <p className="max-w-prose w-full text-lg text-muted-foreground">
          A complete admin dashboard template with 4 apps, 20+ pages, and
          everything wired up using React 19, Next.js 15, and Tailwind CSS 4.
        </p>
        <div className="flex gap-x-2">
          <Link
            href="/dashboards/analytics"
            className={buttonVariants({ size: "lg" })}
          >
            Demo
          </Link>
          <Link
            href="/docs"
            className={buttonVariants({ variant: "secondary", size: "lg" })}
          >
            Documentation
          </Link>
        </div>
      </div>
      <HeroImage />
    </section>
  )
}

function SocialProofBadge() {
  return (
    <a
      href="https://github.com/Qualiora/shadboard"
      className={cn(
        buttonVariants({ variant: "outline", size: "sm" }),
        "group gap-x-1.5"
      )}
      target="_blank"
      rel="noopener noreferrer"
    >
      <AvatarStack
        avatars={SocialProofBadgeAvatarsData}
        size="sm"
        className="me-1.5"
        avatarClassName="h-7 w-7"
      />
      Trusted by 1,000+ developers worldwide
      <ArrowRight className="h-4 w-4 transition-transform duration-200 ease-in-out ltr:group-hover:translate-x-0.5 rtl:scale-x-[-1] rtl:group-hover:-translate-x-0.5" />
    </a>
  )
}

function HeroImage() {
  return (
    <Card className="bg-accent p-3 md:p-6">
      <Card
        className="pointer-events-none bg-muted p-6 overflow-hidden"
        asChild
      >
        <AspectRatio ratio={16 / 9}>
          <Image
            src="/images/misc/hero.png"
            alt=""
            fill
            sizes="(max-width: 768px) 640px, 1080px"
            priority
            className="block object-cover object-top dark:hidden"
          />
          <Image
            src="/images/misc/hero-dark.png"
            alt=""
            fill
            sizes="(max-width: 768px) 640px, 1080px"
            priority
            className="hidden object-cover object-top dark:block"
          />
        </AspectRatio>
      </Card>
    </Card>
  )
}
