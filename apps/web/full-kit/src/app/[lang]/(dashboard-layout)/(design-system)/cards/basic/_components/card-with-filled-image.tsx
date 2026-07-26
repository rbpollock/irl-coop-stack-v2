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

export function CardWithFilledImage() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Smartphone</CardTitle>
        <CardDescription>
          Sleek design, powerful performance, and cutting-edge camera
          technology.
        </CardDescription>
      </CardHeader>
      <CardContent className="px-0">
        <AspectRatio ratio={16 / 9} className="bg-muted">
          <Image
            src="/images/misc/product-04.jpg"
            alt=""
            fill
            sizes="(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 33vw"
            className="h-full w-full object-cover"
          />
        </AspectRatio>
      </CardContent>
      <CardFooter className="flex-col items-start space-y-3">
        <p>
          Stay connected and enjoy seamless multitasking with this premium
          smartphone.
        </p>
        <div className="flex gap-x-2">
          <Button>Buy Now</Button>
          <Button variant="secondary">Learn More</Button>
        </div>
      </CardFooter>
    </Card>
  )
}
