import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

export function ButtonVariants() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Button Variants</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-wrap justify-center items-center gap-2 text-center">
        <div className="space-y-1.5">
          <h4>Primary</h4>
          <Button>Click Here</Button>
        </div>
        <div className="space-y-1.5">
          <h4>Secondary</h4>
          <Button variant="secondary">Secondary</Button>
        </div>
        <div className="space-y-1.5">
          <h4>Ghost</h4>
          <Button variant="ghost">Ghost</Button>
        </div>
        <div className="space-y-1.5">
          <h4>Outline</h4>
          <Button variant="outline">Outline</Button>
        </div>
        <div className="space-y-1.5">
          <h4>Link</h4>
          <Button variant="link">Link</Button>
        </div>
        <div className="space-y-1.5">
          <h4>Destructive</h4>
          <Button variant="destructive">Destructive</Button>
        </div>
      </CardContent>
    </Card>
  )
}
