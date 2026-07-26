import { SiGithub } from "react-icons/si"

import { buttonVariants } from "@/components/ui/button"
import { Card } from "@/components/ui/card"

export function ReadyToBuildCTA() {
  return (
    <section id="ready-to-build" className="container">
      <Card className="flex flex-col justify-center items-center gap-3 text-center px-6 py-12">
        <div className="space-y-1.5">
          <h2 className="text-4xl font-semibold">
            Ready to build your next project faster?
          </h2>
          <p className="max-w-prose mx-auto text-sm text-muted-foreground">
            Get started with our free, open-source admin dashboard template — no
            signup required.
          </p>
        </div>
        <a
          href="https://github.com/Qualiora/shadboard"
          className={buttonVariants({ size: "lg" })}
          target="_blank"
          rel="noopener noreferrer"
        >
          <SiGithub className="me-2 h-4 w-4" />
          View on GitHub
        </a>
      </Card>
    </section>
  )
}
