"use client"

import { useState } from "react"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Rating } from "@/components/ui/rating"

export function RatingIcon() {
  const [rating, setRating] = useState("0")

  return (
    <Card>
      <CardHeader>
        <CardTitle>Rating Icon</CardTitle>
      </CardHeader>
      <CardContent className="grid justify-center gap-2">
        <Rating value={rating} onValueChange={setRating} iconName="Heart" />
        <Rating value={rating} onValueChange={setRating} iconName="Github" />
        <Rating value={rating} onValueChange={setRating} iconName="Egg" />
      </CardContent>
    </Card>
  )
}
