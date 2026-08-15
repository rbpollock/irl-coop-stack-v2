import Image from "next/image"

import { Button } from "@/components/ui/button"
import {
  Card,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"

export function CardOverlay() {
  return (
    <Card className="relative">
      <Image
        src="/images/misc/product-01.jpg"
        alt=""
        fill
        sizes="(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 33vw"
        priority
        className="h-full w-full rounded-lg object-cover"
      />
      <div className="h-full w-full relative flex flex-col justify-between z-20">
        <CardHeader>
          <CardTitle>Bluetooth Headphones</CardTitle>
          <CardDescription>
            High-quality sound, deep bass, and long battery life.
          </CardDescription>
        </CardHeader>
        <CardFooter className="flex-col items-start space-y-3">
          <div className="flex gap-x-2">
            <Button>Buy Now</Button>
            <Button variant="secondary">Learn More</Button>
          </div>
        </CardFooter>
      </div>
    </Card>
  )
}
