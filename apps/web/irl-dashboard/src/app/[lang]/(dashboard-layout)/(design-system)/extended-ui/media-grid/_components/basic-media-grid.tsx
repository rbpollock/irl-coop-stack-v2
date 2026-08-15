"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { MediaGrid } from "@/components/ui/media-grid"

const mediaData = [
  { src: "/images/illustrations/scenes/scene-01.svg", alt: "" },
  { src: "/images/illustrations/scenes/scene-02.svg", alt: "" },
  { src: "/images/illustrations/scenes/scene-03.svg", alt: "" },
  { src: "/images/illustrations/scenes/scene-04.svg", alt: "" },
  { src: "/images/illustrations/scenes/scene-04.svg", alt: "" },
]

export function BasicMediaGrid() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Basic Media Grid</CardTitle>
      </CardHeader>
      <CardContent>
        <MediaGrid data={mediaData} />
      </CardContent>
    </Card>
  )
}
