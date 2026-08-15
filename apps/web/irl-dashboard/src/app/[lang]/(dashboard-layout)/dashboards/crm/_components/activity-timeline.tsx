import { activityTimelineData } from "../_data/activity-timeline"

import { DatePicker } from "@/components/ui/date-picker"
import { DashboardCard } from "@/components/dashboards/dashboard-card"
import { ActivityTimelineList } from "./activity-timeline-list"

export function ActivityTimeline() {
  return (
    <DashboardCard
      title="Activity Timeline"
      period={activityTimelineData.period}
      action={
        <DatePicker
          value={new Date()}
          buttonClassName="w-9 [&_>_svg]:text-foreground [&_>_span]:hidden"
          buttonOptions={{ size: "icon" }}
          popoverContentOptions={{ align: "end" }}
        />
      }
      size="lg"
      contentClassName="pb-0"
    >
      <ActivityTimelineList data={activityTimelineData.activities} />
    </DashboardCard>
  )
}
