"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Rating } from "@/components/ui/rating"

export function RatingReadOnly() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Rating Read Only</CardTitle>
      </CardHeader>
      <CardContent className="grid justify-center gap-2">
        <Rating value="1" readOnly />
        <Rating value="3" readOnly />
        <Rating value="5" readOnly />
      </CardContent>
    </Card>
  )
}
