import { cn } from "@/lib/utils"

import { buttonVariants } from "@/components/ui/button"

export function Footer() {
  const currentYear = new Date().getFullYear()

  return (
    <footer className="bg-background border-t border-sidebar-border">
      <div className="container flex justify-between items-center p-4 md:px-6">
        <p className="text-xs text-muted-foreground md:text-sm">
          © {currentYear}{" "}
          <a
            href="/"
            target="_blank"
            rel="noopener noreferrer"
            className={cn(buttonVariants({ variant: "link" }), "inline p-0")}
          >
            Shadboard
          </a>
          .
        </p>
        <p className="text-xs text-muted-foreground md:text-sm">
          Designed & Developed by{" "}
          <a
            href="https://github.com/Qualiora"
            target="_blank"
            rel="noopener noreferrer"
            className={cn(buttonVariants({ variant: "link" }), "inline p-0")}
          >
            Qualiora
          </a>
          .
        </p>
      </div>
    </footer>
  )
}
