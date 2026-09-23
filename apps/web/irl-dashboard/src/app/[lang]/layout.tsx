import { Cairo, Instrument_Serif, Lato } from "next/font/google"
import { getServerSession } from "next-auth"

import { i18n } from "@/configs/i18n"
import { authOptions } from "@/configs/next-auth"
import { cn } from "@/lib/utils"

import "../globals.css"

import { Providers } from "@/providers"

import type { LocaleType } from "@/types"
import type { Metadata } from "next"
import type { ReactNode } from "react"

import { Toaster as Sonner } from "@/components/ui/sonner"
import { Toaster } from "@/components/ui/toaster"

export const metadata: Metadata = {
  metadataBase: new URL(process.env.BASE_URL as string),
  title: {
    template: "%s | irl.coop",
    default: "irl.coop — We're here for cooperation.",
  },
  description:
    "A member-owned digital cooperative. Share tools, time, skills and space — project management, visual databases, websites and chat under one identity you own. No platform in the middle.",
  applicationName: "irl.coop",
  openGraph: {
    type: "website",
    url: "/",
    siteName: "irl.coop",
    title: "irl.coop — We're here for cooperation.",
    description:
      "A member-owned digital cooperative. Share tools, time, skills and space — under one identity you own.",
    images: [
      {
        url: "/images/og.png",
        width: 1200,
        height: 630,
        alt: "irl.coop — We're here for cooperation.",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "irl.coop — We're here for cooperation.",
    description:
      "A member-owned digital cooperative. Share tools, time, skills and space — under one identity you own.",
    images: ["/images/og.png"],
  },
  icons: {
    icon: [
      { url: "/images/icon.svg", type: "image/svg+xml" },
      { url: "/images/favicon-32.png", type: "image/png", sizes: "32x32" },
      { url: "/images/favicon-16.png", type: "image/png", sizes: "16x16" },
    ],
    apple: [{ url: "/images/apple-touch-icon.png", sizes: "180x180" }],
  },
}

const latoFont = Lato({
  subsets: ["latin"],
  weight: ["100", "300", "400", "700", "900"],
  style: ["normal", "italic"],
  variable: "--font-lato",
})
const cairoFont = Cairo({
  subsets: ["arabic"],
  weight: ["400", "700"],
  style: ["normal"],
  variable: "--font-cairo",
})
const instrumentSerif = Instrument_Serif({
  subsets: ["latin"],
  weight: "400",
  style: ["normal", "italic"],
  variable: "--font-instrument-serif",
})

export default async function RootLayout(props: {
  children: ReactNode
  params: Promise<{ lang: LocaleType }>
}) {
  const params = await props.params
  const { children } = props

  const session = await getServerSession(authOptions)
  const direction = i18n.localeDirection[params.lang]

  return (
    <html lang={params.lang} dir={direction} suppressHydrationWarning>
      <body
        className={cn(
          "[&:lang(en)]:font-lato [&:lang(ar)]:font-cairo",
          "bg-background text-foreground antialiased overscroll-none",
          latoFont.variable,
          cairoFont.variable,
          instrumentSerif.variable
        )}
      >
        <Providers locale={params.lang} direction={direction} session={session}>
          {children}
          <Toaster />
          <Sonner />
        </Providers>
      </body>
    </html>
  )
}
