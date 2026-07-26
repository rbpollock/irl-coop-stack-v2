import { ImageIcon, MapPin, Video } from "lucide-react"

import { userData } from "@/data/user"

import { getInitials } from "@/lib/utils"

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"

export function ProfileContentCreatePost() {
  return (
    <Card asChild>
      <article aria-label="Create a post">
        <div className="grid grid-cols-[2.5rem__auto] gap-x-2 p-6">
          <Avatar>
            <AvatarImage src={userData.avatar} alt="" />
            <AvatarFallback>{getInitials(userData.name)}</AvatarFallback>
          </Avatar>
          <div className="flex gap-x-1.5">
            <Button
              type="button"
              variant="outline"
              size="icon"
              className="flex-1 h-10 justify-start px-3"
            >
              What&apos;s heppening?
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="h-10 w-10 shrink-0"
            >
              <ImageIcon className="h-4 w-4" />
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="h-10 w-10 shrink-0"
            >
              <Video className="h-4 w-4" />
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="h-10 w-10 shrink-0"
            >
              <MapPin className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </article>
    </Card>
  )
}
