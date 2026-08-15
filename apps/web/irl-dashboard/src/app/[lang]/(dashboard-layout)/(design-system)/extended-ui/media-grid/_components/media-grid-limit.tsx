"use client"

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { MediaGrid } from "@/components/ui/media-grid"

const mediaData = [
  { src: "/images/illustrations/scenes/scene-01.svg", alt: "" },
  { src: "/images/illustrations/scenes/scene-02.svg", alt: "" },
  { src: "/images/illustrations/scenes/scene-03.svg", alt: "" },
  { src: "/images/illustrations/scenes/scene-04.svg", alt: "" },
  { src: "/images/illustrations/scenes/scene-04.svg", alt: "" },
]

export function MediaGridLimit() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Media Grid Limit</CardTitle>
        <CardDescription>Set to 2</CardDescription>
      </CardHeader>
      <CardContent>
        <MediaGrid data={mediaData} limit={2} />
      </CardContent>
    </Card>
  )
}
