import type { CoreFeatureType } from "../types"

import { Badge } from "@/components/ui/badge"
import {
  BentoContent,
  BentoDescription,
  BentoItem,
  BentoTitle,
} from "@/components/ui/bento-grid"

export function CoreFeaturesItem({ feature }: { feature: CoreFeatureType }) {
  return (
    <BentoItem className={feature.className}>
      <BentoContent>
        <Badge className="size-12 aspect-square" aria-hidden>
          <feature.icon className="size-full" />
        </Badge>
        <BentoTitle>{feature.title}</BentoTitle>
        <BentoDescription>{feature.description}</BentoDescription>
      </BentoContent>
      {feature?.header && feature.header}
    </BentoItem>
  )
}
