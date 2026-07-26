"use client"

import { avatarsData } from "../_data/avatars"

import { AvatarStack } from "@/components/ui/avatar"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

export function BasicAvatarStack() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Basic Avatar Stack</CardTitle>
      </CardHeader>
      <CardContent className="flex justify-center items-center">
        <AvatarStack avatars={avatarsData} />
      </CardContent>
    </Card>
  )
}
