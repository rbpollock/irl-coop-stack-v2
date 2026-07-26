"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { InputPhone } from "@/components/ui/input-phone"

export function BasicInputPhoneCountry() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Input Phone Country</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col justify-center items-center gap-2">
        <div className="flex flex-col items-center space-y-1.5">
          <h4>Default (International)</h4>
          <InputPhone className="max-w-72" />
        </div>
        <div className="flex flex-col items-center space-y-1.5">
          <h4>Local (Default Country set to US)</h4>
          <InputPhone className="max-w-72" defaultCountry="US" />
        </div>
      </CardContent>
    </Card>
  )
}
