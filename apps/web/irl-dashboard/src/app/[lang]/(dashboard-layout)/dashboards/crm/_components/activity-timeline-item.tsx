import type { ActivityTimelineType } from "../types"

import { formatTime } from "@/lib/utils"

import { AvatarStack } from "@/components/ui/avatar"
import { Badge } from "@/components/ui/badge"
import {
  TimelineContent,
  TimelineDot,
  TimelineHeading,
  TimelineItem,
  TimelineLine,
} from "@/components/ui/timeline"

function RenderAvatarStack({
  assignedMembers,
}: {
  assignedMembers: Array<{
    name: string
    avatar: string
    href: string
  }>
}) {
  if (assignedMembers && assignedMembers.length > 0) {
    return (
      <AvatarStack
        avatars={assignedMembers.map((member) => ({
          src: member.avatar,
          alt: member.name,
          href: member.href,
        }))}
      />
    )
  }

  return null
}

export function ActivityTimelineItem({
  data,
  isLast,
}: {
  data: ActivityTimelineType["activities"][number]
  isLast: boolean
}) {
  return (
    <TimelineItem>
      <TimelineHeading>{data.title}</TimelineHeading>
      <TimelineDot
        style={{
          backgroundColor: data.fill || "hsl(var(--muted-foreground))",
        }}
        customIconName={data.iconName}
        customStatusName={data.type}
        iconClassName="size-6 text-background p-1"
      />
      {isLast && <TimelineLine />}
      <TimelineContent className="space-y-2">
        <div className="flex items-center text-sm text-muted-foreground">
          <span>{formatTime(data.date)}</span>
          {data.status && (
            <Badge variant="outline" className="ms-2">
              {data.status}
            </Badge>
          )}
        </div>
        <p className="text-sm">{data.description}</p>
        <RenderAvatarStack assignedMembers={data.assignedMembers} />
      </TimelineContent>
    </TimelineItem>
  )
}
