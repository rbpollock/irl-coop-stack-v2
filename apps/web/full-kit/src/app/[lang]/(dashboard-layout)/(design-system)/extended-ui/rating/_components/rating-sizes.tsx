"use client"

import { useState } from "react"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Rating } from "@/components/ui/rating"

export function RatingSizes() {
  const [rating, setRating] = useState("0")

  return (
    <Card>
      <CardHeader>
        <CardTitle>Rating Sizes</CardTitle>
      </CardHeader>
      <CardContent className="grid justify-center gap-2">
        <div className="space-y-1.5">
          <h4>Default</h4>
          <Rating value={rating} onValueChange={setRating} />
        </div>
        <div className="space-y-1.5">
          <h4>Small</h4>
          <Rating size="sm" value={rating} onValueChange={setRating} />
        </div>
        <div className="space-y-1.5">
          <h4>Large</h4>
          <Rating size="lg" value={rating} onValueChange={setRating} />
        </div>
      </CardContent>
    </Card>
  )
}
