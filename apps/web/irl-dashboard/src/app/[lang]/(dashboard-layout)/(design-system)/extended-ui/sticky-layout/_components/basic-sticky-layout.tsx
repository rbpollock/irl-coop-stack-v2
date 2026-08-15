import Image from "next/image"

import { AspectRatio } from "@/components/ui/aspect-ratio"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  StickyLayout,
  StickyLayoutContent,
  StickyLayoutPane,
} from "@/components/ui/sticky-layout"

export function BasicStickyLayout() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Basic Sticky Layout</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-4">
        <StickyLayout>
          <StickyLayoutPane>
            <h3 className="text-2xl font-semibold">Title 1</h3>
            <p className="max-w-prose text-sm text-muted-foreground">
              Description 1
            </p>
          </StickyLayoutPane>
          <StickyLayoutContent>
            <Card className="bg-muted overflow-hidden" asChild>
              <AspectRatio ratio={1 / 1}>
                <Image
                  src="/images/illustrations/scenes/scene-01.svg"
                  alt=""
                  fill
                  sizes="(max-width: 768px) 100vw, 768px"
                  className="object-cover bg-white dark:invert"
                />
              </AspectRatio>
            </Card>
            <Card className="bg-muted overflow-hidden" asChild>
              <AspectRatio ratio={1 / 1}>
                <Image
                  src="/images/illustrations/scenes/scene-02.svg"
                  alt=""
                  fill
                  sizes="(max-width: 768px) 100vw, 768px"
                  className="object-cover bg-white dark:invert"
                />
              </AspectRatio>
            </Card>
          </StickyLayoutContent>
        </StickyLayout>
        <StickyLayout>
          <StickyLayoutPane>
            <h3 className="text-2xl font-semibold">Title 2</h3>
            <p className="max-w-prose text-sm text-muted-foreground">
              Description 2
            </p>
          </StickyLayoutPane>
          <StickyLayoutContent>
            <Card className="bg-muted overflow-hidden" asChild>
              <AspectRatio ratio={1 / 1}>
                <Image
                  src="/images/illustrations/scenes/scene-03.svg"
                  alt=""
                  fill
                  sizes="(max-width: 768px) 100vw, 768px"
                  className="object-cover bg-white dark:invert"
                />
              </AspectRatio>
            </Card>
            <Card className="bg-muted overflow-hidden" asChild>
              <AspectRatio ratio={1 / 1}>
                <Image
                  src="/images/illustrations/scenes/scene-04.svg"
                  alt=""
                  fill
                  sizes="(max-width: 768px) 100vw, 768px"
                  className="object-cover bg-white dark:invert"
                />
              </AspectRatio>
            </Card>
          </StickyLayoutContent>
        </StickyLayout>
      </CardContent>
    </Card>
  )
}
