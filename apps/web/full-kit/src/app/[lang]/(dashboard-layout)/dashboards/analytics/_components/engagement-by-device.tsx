import { engagementByDeviceData } from "../_data/engagement-by-device"

import { EngagementByDeviceTable } from "./engagement-by-device-table"

export function EngagementByDevice() {
  return (
    <article className="col-span-full">
      <EngagementByDeviceTable data={engagementByDeviceData} />
    </article>
  )
}
