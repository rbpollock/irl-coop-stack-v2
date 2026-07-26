import { overviewData } from "../../_data/overview"

import { AverageSessionDuration } from "./average-session-duration"
import { BounceRate } from "./bounce-rate"
import { ConversionRate } from "./conversion-rate"
import { UniqueVisitors } from "./unique-visitors"

export function Overview() {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 md:col-span-full md:grid-cols-4">
      <UniqueVisitors data={overviewData.uniqueVisitors} />
      <AverageSessionDuration data={overviewData.averageSessionDuration} />
      <BounceRate data={overviewData.bounceRate} />
      <ConversionRate data={overviewData.conversionRate} />
    </div>
  )
}
