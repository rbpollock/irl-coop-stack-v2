import {
  EllipsisVertical,
  Forward,
  MessagesSquare,
  Repeat,
  ThumbsUp,
} from "lucide-react"

import type {
  PostType,
  VisibilityType,
} from "@/app/[lang]/(dashboard-layout)/pages/account/types"
import type { DynamicIconNameType } from "@/types"

import { formatDistance, formatNumberToCompact, getInitials } from "@/lib/utils"

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { MediaGrid } from "@/components/ui/media-grid"
import { Separator } from "@/components/ui/separator"
import { Toggle } from "@/components/ui/toggle"
import { DynamicIcon } from "@/components/dynamic-icon"

const visibilityIcons: Record<VisibilityType, DynamicIconNameType> = {
  public: "Globe",
  friends: "Users",
  private: "Lock",
}

export function ProfileContentPostItem({ data }: { data: PostType }) {
  return (
    <Card asChild>
      <article aria-label="Create a post">
        <CardHeader className="flex-row justify-between items-center gap-x-3 space-y-0">
          <div className="flex items-center gap-x-2">
            <Avatar>
              <AvatarImage src={data.user.avatar} alt="" />
              <AvatarFallback>{getInitials(data.user.name)}</AvatarFallback>
            </Avatar>
            <div>
              <CardTitle>{data.user.name}</CardTitle>
              <CardDescription className="inline-flex items-baseline">
                <span className="after:content-['\00b7'] after:mx-1">
                  {formatDistance(data.updatedAt)}
                </span>
                <DynamicIcon
                  name={visibilityIcons[data.visibility]}
                  className="h-3 w-3 translate-y-[0.125rem]"
                />
              </CardDescription>
            </div>
          </div>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="shrink-0"
          >
            <EllipsisVertical className="h-4 w-4" />
          </Button>
        </CardHeader>
        <CardContent>
          {data.text && <p>{data.text}</p>}
          {data.media && <MediaGrid className="mt-2" data={data.media} />}
        </CardContent>
        <CardFooter className="grid gap-y-1.5 pb-3">
          <div className="w-full flex justify-between text-sm text-muted-foreground">
            <p>{formatNumberToCompact(data.totalLikes)} likes</p>
            <div className="inline-flex">
              <p className="after:content-['\00b7'] after:mx-1">
                {formatNumberToCompact(data.totalComments)} comments
              </p>
              <p>{formatNumberToCompact(data.totalReposts)} reposts</p>
            </div>
          </div>
          <Separator orientation="horizontal" />
          <div className="grid grid-cols-4 gap-x-1.5">
            <Toggle
              type="button"
              size="lg"
              className="flex-col items-center hover:text-accent-foreground md:flex-row"
              defaultPressed={data.isLiked}
            >
              <ThumbsUp className="h-4 w-4 shrink-0 md:me-2" />
              <span>Like</span>
            </Toggle>
            <Button
              type="button"
              variant="ghost"
              size="lg"
              className="flex-col md:flex-row"
            >
              <MessagesSquare className="h-4 w-4 shrink-0 md:me-2" />
              <span>Comment</span>
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="lg"
              className="flex-col md:flex-row"
            >
              <Repeat className="h-4 w-4 shrink-0 md:me-2" />
              <span>Repost</span>
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="lg"
              className="flex-col md:flex-row"
            >
              <Forward className="h-4 w-4 shrink-0 md:me-2" />
              <span>Share</span>
            </Button>
          </div>
        </CardFooter>
      </article>
    </Card>
  )
}
