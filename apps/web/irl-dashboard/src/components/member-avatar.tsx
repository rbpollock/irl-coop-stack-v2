import { dicebearAvatar } from "@/lib/dicebear"
import { getInitials } from "@/lib/utils"

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"

// A member avatar with a deterministic self-hosted DiceBear default: if the
// member has set a custom image (`avatar`), use it; otherwise render the
// DiceBear glyphs avatar derived from their stable `sub`. Works in both server
// and client components (DiceBear renders synchronously, no fetch).
export function MemberAvatar({
  sub,
  avatar,
  name,
  className,
  imageClassName,
}: {
  sub?: string | null
  avatar?: string | null
  name?: string | null
  className?: string
  imageClassName?: string
}) {
  const src = avatar || (sub ? dicebearAvatar(sub) : undefined)
  return (
    <Avatar className={className}>
      {src && (
        <AvatarImage src={src} alt={name ?? ""} className={imageClassName} />
      )}
      <AvatarFallback className="bg-transparent">
        {name ? getInitials(name) : null}
      </AvatarFallback>
    </Avatar>
  )
}
