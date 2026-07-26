import { coreFeaturesData } from "../_data/core-features"

import { BentoGrid } from "@/components/ui/bento-grid"
import { CoreFeaturesItem } from "./core-features-item"

export function CoreFeaturesList() {
  return (
    <BentoGrid>
      {coreFeaturesData.map((feature) => (
        <CoreFeaturesItem key={feature.title} feature={feature} />
      ))}
    </BentoGrid>
  )
}
