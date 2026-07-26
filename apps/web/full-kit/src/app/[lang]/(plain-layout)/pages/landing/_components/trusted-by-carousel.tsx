"use client"

import Image from "next/image"
import { useDirection } from "@radix-ui/react-direction"
import Autoplay from "embla-carousel-autoplay"

import { trustedByData } from "../_data/trusted-by"

import { Card } from "@/components/ui/card"
import {
  Carousel,
  CarouselContent,
  CarouselItem,
} from "@/components/ui/carousel"

export function TrustedByCarousel() {
  const direction = useDirection()

  return (
    <Card className="py-6 bg-accent" asChild>
      <Carousel
        plugins={[
          Autoplay({
            delay: 2500,
            stopOnInteraction: false,
          }),
        ]}
        opts={{
          align: "center",
          loop: true,
          direction,
        }}
        className="select-none"
      >
        <CarouselContent>
          {trustedByData.map((company) => (
            <CarouselItem key={company.name} className="basis-1/4 md:basis-1/8">
              <Image
                src={company.logoSrc}
                alt={company.alt}
                width={124}
                height={124}
                className="max-h-12 h-full grayscale opacity-80 dark:invert"
              />
            </CarouselItem>
          ))}
        </CarouselContent>
      </Carousel>
    </Card>
  )
}
