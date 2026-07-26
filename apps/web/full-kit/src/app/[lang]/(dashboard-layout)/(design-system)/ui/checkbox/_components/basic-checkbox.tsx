import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"

export function BasicCheckbox() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Basic Checkbox</CardTitle>
      </CardHeader>
      <CardContent className="grid justify-center gap-2">
        <div className="flex items-center gap-x-2">
          <Checkbox id="terms" />
          <label
            htmlFor="terms"
            className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
          >
            Accept terms and conditions
          </label>
        </div>
        <div className="flex items-center gap-x-2">
          <Checkbox id="terms2" checked />
          <label
            htmlFor="terms2"
            className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
          >
            Accept terms and conditions
          </label>
        </div>
      </CardContent>
    </Card>
  )
}
