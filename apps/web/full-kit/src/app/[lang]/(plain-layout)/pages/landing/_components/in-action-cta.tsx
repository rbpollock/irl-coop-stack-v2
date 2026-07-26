import Link from "next/link"

import { buttonVariants } from "@/components/ui/button"
import { Card } from "@/components/ui/card"

export function InActionCTA() {
  return (
    <section id="ready-to-build" className="container">
      <Card className="flex flex-col justify-evenly items-center gap-3 text-center px-6 py-12 md:flex-row md:text-start">
        <div className="space-y-1.5">
          <h2 className="text-4xl font-semibold">
            Want to see Shadboard in action?
          </h2>
          <p className="max-w-prose mx-auto text-sm text-muted-foreground">
            Explore the live demo or check out the documentation to learn how
            Shadboard can speed up your development.
          </p>
        </div>
        <div className="flex gap-2 md:flex-col">
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
      </Card>
    </section>
  )
}
