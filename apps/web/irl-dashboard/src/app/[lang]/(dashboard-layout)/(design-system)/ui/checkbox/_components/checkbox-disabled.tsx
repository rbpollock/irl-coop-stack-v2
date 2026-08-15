import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"

export function CheckboxDisabled() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Checkbox Disabled</CardTitle>
      </CardHeader>
      <CardContent className="grid justify-center gap-2">
        <div className="flex items-center gap-x-2">
          <Checkbox id="terms3" disabled />
          <label
            htmlFor="terms3"
            className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
          >
            Accept terms and conditions
          </label>
        </div>
        <div className="flex items-center gap-x-2">
          <Checkbox id="terms4" checked disabled />
          <label
            htmlFor="terms4"
            className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
          >
            Accept terms and conditions
          </label>
        </div>
      </CardContent>
    </Card>
  )
}
