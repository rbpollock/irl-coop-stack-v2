import { Lato } from "next/font/google"

import { cn } from "@/lib/utils"

import "../globals.css"

import { Providers } from "@/providers"

import type { Metadata } from "next"
import type { ReactNode } from "react"

import { Toaster as Sonner } from "@/components/ui/sonner"
import { Toaster } from "@/components/ui/toaster"

export const metadata: Metadata = {
  metadataBase: new URL(process.env.BASE_URL as string),
  title: {
    template: "%s | irl.coop",
    default: "irl.coop",
  },
  description:
    "A member-owned digital cooperative. Share tools, time, skills and space — under one identity you own.",
  applicationName: "irl.coop",
  openGraph: {
    type: "website",
    siteName: "irl.coop",
    title: "irl.coop — We're here for cooperation.",
    description:
      "A member-owned digital cooperative. Share tools, time, skills and space — under one identity you own.",
    images: [{ url: "/images/og.png", width: 1200, height: 630 }],
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

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body
        className={cn(
          "[&:lang(en)]:font-lato",
          "bg-background text-foreground antialiased overscroll-none",
          latoFont.variable
        )}
      >
        <Providers locale="en" direction="ltr" session={null}>
          {children}
          <Toaster />
          <Sonner />
        </Providers>
      </body>
    </html>
  )
}
