import Image from "next/image"
import { Check } from "lucide-react"

import type { CoreBenefitType } from "../types"

import { AspectRatio } from "@/components/ui/aspect-ratio"
import { Card } from "@/components/ui/card"
import {
  StickyLayout,
  StickyLayoutContent,
  StickyLayoutPane,
} from "@/components/ui/sticky-layout"

export function CoreBenefitsItem({ benefit }: { benefit: CoreBenefitType }) {
  return (
    <Card className="p-6" asChild>
      <StickyLayout asChild>
        <li>
          <StickyLayoutPane>
            <h3 className="text-2xl font-semibold">{benefit.title}</h3>
            <p className="max-w-prose text-sm text-muted-foreground">
              {benefit.description}
            </p>
            <ul className="inline-block w-full mt-4 space-y-4 lg:max-w-prose lg:mt-2">
              {benefit.points.map((point) => (
                <Card key={point} asChild>
                  <li className="flex items-center gap-x-3 p-6 !bg-accent text-accent-foreground">
                    <Check className="shrink-0 size-4 text-success" />
                    <span>{point}</span>
                  </li>
                </Card>
              ))}
            </ul>
          </StickyLayoutPane>
          <StickyLayoutContent>
            {benefit.images.map((image) => (
              <Card key={image} className="bg-muted overflow-hidden" asChild>
                <AspectRatio ratio={1 / 1}>
                  <Image
                    src={image}
                    alt=""
                    fill
                    sizes="(max-width: 768px) 100vw, 768px"
                    className="object-cover bg-white dark:invert"
                  />
                </AspectRatio>
              </Card>
            ))}
          </StickyLayoutContent>
        </li>
      </StickyLayout>
    </Card>
  )
}
