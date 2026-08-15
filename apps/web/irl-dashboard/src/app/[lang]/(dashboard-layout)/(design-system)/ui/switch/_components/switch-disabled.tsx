"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"

export function SwitchDisabled() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Switch Disabled</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-2">
        <div className="flex justify-center items-center gap-x-2">
          <Switch id="switch3" disabled />
          <Label htmlFor="switch3">Airplane Mode</Label>
        </div>
        <div className="flex justify-center items-center gap-x-2">
          <Switch id="switch4" checked disabled />
          <Label htmlFor="switch4">Airplane Mode</Label>
        </div>
      </CardContent>
    </Card>
  )
}
