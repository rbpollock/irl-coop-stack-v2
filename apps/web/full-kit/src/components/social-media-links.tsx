import { socialLinksData } from "@/data/social-links"

import { Button } from "@/components/ui/button"

export function SocialMediaLinks() {
  return (
    <div className="flex justify-center gap-2">
      {socialLinksData.map(({ href, label, icon: Icon }) => (
        <Button key={label} variant="outline" size="icon" asChild>
          <a
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            aria-label={label}
          >
            <Icon className="size-4" />
          </a>
        </Button>
      ))}
    </div>
  )
}
