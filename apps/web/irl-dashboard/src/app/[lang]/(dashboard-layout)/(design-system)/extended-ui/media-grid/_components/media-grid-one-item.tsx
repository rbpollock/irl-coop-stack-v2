"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { MediaGrid } from "@/components/ui/media-grid"

const mediaData = [
  { src: "/images/illustrations/scenes/scene-01.svg", alt: "" },
]

export function MediaGridOneItem() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Media Grid One Item</CardTitle>
      </CardHeader>
      <CardContent>
        <MediaGrid data={mediaData} />
      </CardContent>
    </Card>
  )
}
