"use client"

import { useState } from "react"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Rating } from "@/components/ui/rating"

export function RatingLength() {
  const [rating, setRating] = useState("0")

  return (
    <Card>
      <CardHeader>
        <CardTitle>Rating Length</CardTitle>
      </CardHeader>
      <CardContent className="grid justify-center gap-2">
        <Rating value={rating} onValueChange={setRating} />
        <Rating value={rating} onValueChange={setRating} length={4} />
        <Rating value={rating} onValueChange={setRating} length={3} />
      </CardContent>
    </Card>
  )
}
