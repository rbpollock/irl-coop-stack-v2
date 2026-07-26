import type { ActivityTimelineType } from "../types"

import { ScrollArea } from "@/components/ui/scroll-area"
import { Timeline } from "@/components/ui/timeline"
import { ActivityTimelineItem } from "./activity-timeline-item"

export function ActivityTimelineList({
  data,
}: {
  data: ActivityTimelineType["activities"]
}) {
  return (
    <ScrollArea>
      {data.length ? (
        <Timeline>
          {data.map((activity, index) => {
            const isLast = index !== data.length - 1

            return (
              <ActivityTimelineItem
                key={activity.title}
                data={activity}
                isLast={isLast}
              />
            )
          })}
        </Timeline>
      ) : (
        <div className="text-center py-8 text-muted-foreground">
          No activities found
        </div>
      )}
    </ScrollArea>
  )
}
