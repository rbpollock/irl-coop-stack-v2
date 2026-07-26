import Image from "next/image"

import { AspectRatio } from "@/components/ui/aspect-ratio"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"

export function CardWithFilledImageHorizontal() {
  return (
    <Card className="grid grid-cols-5">
      <CardHeader className="col-span-2 p-0 pe-6">
        <AspectRatio ratio={1 / 1} className="bg-muted">
          <Image
            src="/images/misc/product-03.jpg"
            alt=""
            fill
            sizes="(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 33vw"
            className="h-full w-full rounded-s-lg object-cover"
          />
        </AspectRatio>
      </CardHeader>
      <div className="col-span-3 flex flex-col justify-between gap-y-3 p-6 ps-0">
        <CardContent className="p-0 space-y-1.5">
          <CardTitle>Mirrorless Camera</CardTitle>
          <CardDescription className="line-clamp-2">
            Capture stunning photos and videos with this lightweight,
            high-performance mirrorless camera.
          </CardDescription>
        </CardContent>
        <CardFooter className="gap-x-3 p-0">
          <Button>Buy Now</Button>
          <Button variant="secondary">Learn More</Button>
        </CardFooter>
      </div>
    </Card>
  )
}
