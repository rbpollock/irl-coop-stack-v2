"use client"

import { useDirection } from "@radix-ui/react-direction"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Carousel,
  CarouselContent,
  CarouselItem,
  CarouselNext,
  CarouselPrevious,
} from "@/components/ui/carousel"

export function CarouselSizes() {
  const direction = useDirection()

  return (
    <Card>
      <CardHeader>
        <CardTitle>Carousel Sizes</CardTitle>
      </CardHeader>
      <CardContent className="flex justify-center items-center">
        <Carousel
          opts={{
            align: "start",
            direction,
          }}
          className="w-full max-w-sm grid"
        >
          <CarouselContent>
            {Array.from({ length: 5 }).map((_, index) => (
              <CarouselItem key={index} className="md:basis-1/2 lg:basis-1/3">
                <div className="p-1">
                  <Card>
                    <CardContent className="flex aspect-square items-center justify-center p-6">
                      <span className="text-3xl font-semibold">
                        {index + 1}
                      </span>
                    </CardContent>
                  </Card>
                </div>
              </CarouselItem>
            ))}
          </CarouselContent>
          <CarouselPrevious />
          <CarouselNext />
        </Carousel>
      </CardContent>
    </Card>
  )
}
