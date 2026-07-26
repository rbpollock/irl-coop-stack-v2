"use client"

import { avatarsData } from "../_data/avatars"

import { AvatarStack } from "@/components/ui/avatar"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

export function AvatarStackSize() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Avatar Stack Size</CardTitle>
      </CardHeader>
      <CardContent className="grid justify-center gap-2">
        <div className="space-y-1.5">
          <h4>Default</h4>
          <AvatarStack avatars={avatarsData} />
        </div>
        <div className="space-y-1.5">
          <h4>Small</h4>
          <AvatarStack avatars={avatarsData} size="sm" />
        </div>
        <div className="space-y-1.5">
          <h4>Large</h4>
          <AvatarStack avatars={avatarsData} size="lg" />
        </div>
      </CardContent>
    </Card>
  )
}
