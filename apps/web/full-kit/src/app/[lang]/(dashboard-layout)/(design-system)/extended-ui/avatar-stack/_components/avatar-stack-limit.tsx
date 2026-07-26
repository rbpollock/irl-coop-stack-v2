"use client"

import { avatarsData } from "../_data/avatars"

import { AvatarStack } from "@/components/ui/avatar"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

export function AvatarStackLimit() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Avatar Stack Limit</CardTitle>
      </CardHeader>
      <CardContent className="grid justify-center gap-2">
        <AvatarStack avatars={avatarsData} limit={2} />
        <AvatarStack avatars={avatarsData} limit={3} />
      </CardContent>
    </Card>
  )
}
