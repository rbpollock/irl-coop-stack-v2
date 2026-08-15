"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"

export function BasicSwitch() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Basic Switch</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-2">
        <div className="flex justify-center items-center gap-x-2">
          <Switch id="switch" />
          <Label htmlFor="switch">Airplane Mode</Label>
        </div>
        <div className="flex justify-center items-center gap-x-2">
          <Switch id="switch2" checked />
          <Label htmlFor="switch2">Airplane Mode</Label>
        </div>
      </CardContent>
    </Card>
  )
}
