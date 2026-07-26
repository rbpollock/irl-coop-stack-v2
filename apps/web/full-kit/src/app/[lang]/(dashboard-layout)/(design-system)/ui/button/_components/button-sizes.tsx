import { ChevronRight } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

export function ButtonSizes() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Button Sizes</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-wrap justify-center items-center gap-2 text-center">
        <div className="space-y-1.5">
          <h4>Default</h4>
          <Button variant="outline">Default</Button>
        </div>
        <div className="space-y-1.5">
          <h4>Icon</h4>
          <Button variant="outline" size="icon">
            <ChevronRight />
          </Button>
        </div>
        <div className="space-y-1.5">
          <h4>Small</h4>
          <Button variant="outline" size="sm">
            Small
          </Button>
        </div>
        <div className="space-y-1.5">
          <h4>Large</h4>
          <Button variant="outline" size="lg">
            Large
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
