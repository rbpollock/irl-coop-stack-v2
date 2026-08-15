import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

export function BasicBadge() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Basic Badge</CardTitle>
      </CardHeader>
      <CardContent className="flex justify-center items-center gap-2">
        <Badge>Badge</Badge>
        <Badge variant="destructive">Destructive</Badge>
        <Badge variant="outline">Outline</Badge>
        <Badge variant="secondary">Secondary</Badge>
      </CardContent>
    </Card>
  )
}
