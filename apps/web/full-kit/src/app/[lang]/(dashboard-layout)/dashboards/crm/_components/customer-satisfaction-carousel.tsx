"use client"

import { useDirection } from "@radix-ui/react-direction"
import Autoplay from "embla-carousel-autoplay"

import type { CustomerSatisfactionType } from "../types"

import { formatDate, getInitials } from "@/lib/utils"

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

export function CustomerSatisfactionCarousel({
  data,
}: {
  data: CustomerSatisfactionType["feedbacks"]
}) {
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
      className="w-[calc(100vw-190px)] mx-14 select-none md:w-3/6"
    >
      <CarouselContent>
        {data.map((feedback) => (
          <CarouselItem key={feedback.name}>
            <Card className="flex flex-col">
              <CardHeader className="flex-row items-center gap-4 p-3">
                <Avatar className="h-12 w-12">
                  <AvatarImage src={feedback.avatar} alt={feedback.name} />
                  <AvatarFallback>{getInitials(feedback.name)}</AvatarFallback>
                </Avatar>
                <div className="overflow-hidden">
                  <CardTitle className="text-sm font-semibold break-all truncate">
                    {feedback.name}
                  </CardTitle>
                  <p className="text-xs text-muted-foreground font-semibold break-all truncate">
                    {feedback.email}
                  </p>
                </div>
              </CardHeader>
              <Separator />
              <CardContent className="space-y-1.5 p-3">
                <div className="flex flex-wrap justify-between items-center gap-2">
                  <div className="flex items-center gap-2">
                    <Badge aria-hidden>{feedback.rating.toFixed(1)}</Badge>
                    <Rating value={feedback.rating.toString()} readOnly />
                  </div>
                  <p className="text-sm text-muted-foreground">
                    {formatDate(feedback.createdAt)}
                  </p>
                </div>
                <ScrollArea className="h-20">
                  <ShowMoreText
                    text={feedback.feedbackMessage}
                    className="text-sm break-all"
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
