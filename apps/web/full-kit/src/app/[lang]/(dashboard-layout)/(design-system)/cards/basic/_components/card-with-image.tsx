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

export function CardWithImage() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Bluetooth Headphones</CardTitle>
        <CardDescription>
          High-quality sound, deep bass, and long battery life.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <AspectRatio ratio={16 / 9} className="bg-muted rounded-lg">
          <Image
            src="/images/misc/product-01.jpg"
            alt=""
            fill
            sizes="(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 33vw"
            priority
            className="h-full w-full rounded-lg object-cover"
          />
        </AspectRatio>
      </CardContent>
      <CardFooter className="flex-col items-start space-y-3">
        <p>
          Experience immersive audio with this compact and stylish Bluetooth
          Headphones.
        </p>
        <div className="flex gap-x-2">
          <Button>Buy Now</Button>
          <Button variant="secondary">Learn More</Button>
        </div>
      </CardFooter>
    </Card>
  )
}
