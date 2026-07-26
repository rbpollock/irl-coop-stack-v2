import Link from "next/link"

import { cn } from "@/lib/utils"

import { buttonVariants } from "@/components/ui/button"
import { FaqsList } from "./faqs-list"

export function Faqs() {
  return (
    <section id="faqs" className="container grid gap-8 md:grid-cols-3">
      <div className="text-center mx-auto space-y-1.5 md:text-start">
        <h2 className="text-4xl font-semibold">Frequently Asked Questions</h2>
        <p className="max-w-prose text-sm text-muted-foreground">
          Explore answers to common questions. If you need further assistance,{" "}
          <Link
            href="/pages/landing#contact-us"
            className={cn(
              buttonVariants({ variant: "link" }),
              "inline h-fit p-0"
            )}
          >
            get in touch
          </Link>
          .
        </p>
      </div>
      <FaqsList />
    </section>
  )
}
