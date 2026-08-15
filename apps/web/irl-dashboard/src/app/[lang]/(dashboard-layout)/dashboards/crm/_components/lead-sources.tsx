import { leadSourcesData } from "../_data/lead-sources"

import { Card } from "@/components/ui/card"
import { LeadSourcesChart } from "./lead-sources-chart"

export function LeadSources() {
  return (
    <Card className="h-56 p-6">
      <LeadSourcesChart
        data={{
          leads: leadSourcesData.leads,
          summary: leadSourcesData.summary,
        }}
      />
    </Card>
  )
}
