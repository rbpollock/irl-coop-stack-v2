"use client"

import { useDirection } from "@radix-ui/react-direction"
import Autoplay from "embla-carousel-autoplay"

import { whatPeopleSayData } from "../_data/what-people-say"

import { getInitials } from "@/lib/utils"

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Carousel,
  CarouselContent,
  CarouselItem,
  CarouselNext,
  CarouselPrevious,
} from "@/components/ui/carousel"
import { Rating } from "@/components/ui/rating"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"
import { ShowMoreText } from "@/components/ui/show-more-text"

export function WhatPeopleSayCarousel() {
  const direction = useDirection()

  return (
    <Carousel
      plugins={[
        Autoplay({
          delay: 2500,
          stopOnInteraction: false,
          stopOnMouseEnter: true,
        }),
      ]}
      opts={{
        align: "center",
        loop: true,
        direction,
      }}
      className="mx-14 select-none"
    >
      <CarouselContent>
        {whatPeopleSayData.map((person) => (
          <CarouselItem key={person.name} className="lg:basis-1/3">
            <Card className="flex flex-col">
              <CardHeader className="flex-row items-center gap-4 p-3">
                <Avatar className="h-12 w-12">
                  <AvatarImage src={person.avatar} alt={person.name} />
                  <AvatarFallback>{getInitials(person.name)}</AvatarFallback>
                </Avatar>
                <div className="overflow-hidden">
                  <CardTitle className="font-semibold break-all truncate">
                    {person.name}
                  </CardTitle>
                  <p className="text-sm text-muted-foreground break-all truncate">
                    <span className="after:content-['\00b7'] after:mx-1">
                      {person.company}
                    </span>
                    <span>{person.role}</span>
                  </p>
                </div>
              </CardHeader>
              <Separator />
              <CardContent className="space-y-1.5 p-3">
                <div className="flex items-center gap-2">
                  <Badge aria-hidden>{person.rating.toFixed(1)}</Badge>
                  <Rating value={person.rating.toString()} readOnly />
                </div>
                <ScrollArea className="h-20">
                  <ShowMoreText
                    text={person.quote}
                    className="text-sm text-muted-foreground break-words"
                    maxLength={130}
                  />
                </ScrollArea>
              </CardContent>
            </Card>
          </CarouselItem>
        ))}
      </CarouselContent>
      <CarouselPrevious />
      <CarouselNext />
    </Carousel>
  )
}
