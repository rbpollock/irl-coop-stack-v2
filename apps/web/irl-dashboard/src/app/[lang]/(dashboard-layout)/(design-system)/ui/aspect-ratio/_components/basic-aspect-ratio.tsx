import Image from "next/image"

import { AspectRatio } from "@/components/ui/aspect-ratio"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

export function BasicAspectRatio() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Basic Aspect Ratio</CardTitle>
      </CardHeader>
      <CardContent>
        <AspectRatio ratio={16 / 9} className="bg-muted">
          <Image
            src="/images/misc/product-01.jpg"
            alt=""
            fill
            className="h-full w-full rounded-md object-cover"
          />
        </AspectRatio>
      </CardContent>
    </Card>
  )
}
