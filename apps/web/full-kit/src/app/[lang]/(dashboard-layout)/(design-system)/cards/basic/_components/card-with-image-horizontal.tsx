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

export function CardWithImageHorizontal() {
  return (
    <Card className="grid grid-cols-5">
      <CardHeader className="col-span-2">
        <AspectRatio ratio={1 / 1} className="bg-muted rounded-lg">
          <Image
            src="/images/misc/product-02.jpg"
            alt=""
            fill
            sizes="(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 33vw"
            className="h-full w-full rounded-lg object-cover"
          />
        </AspectRatio>
      </CardHeader>
      <div className="col-span-3 flex flex-col justify-between gap-y-3 py-6 pe-6">
        <CardContent className="p-0 space-y-1.5">
          <CardTitle>Smartwatch</CardTitle>
          <CardDescription className="line-clamp-3">
            Stay connected and track your fitness goals with this stylish
            smartwatch featuring heart rate monitoring, GPS, and seamless
            smartphone integration.
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
