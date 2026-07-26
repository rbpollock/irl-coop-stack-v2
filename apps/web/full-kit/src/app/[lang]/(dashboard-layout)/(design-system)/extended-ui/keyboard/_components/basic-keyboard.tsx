"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Keyboard } from "@/components/ui/keyboard"

export function BasicKeyboard() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Basic Keyboard</CardTitle>
      </CardHeader>
      <CardContent className="flex justify-center items-center">
        <Keyboard>K</Keyboard>
      </CardContent>
    </Card>
  )
}
