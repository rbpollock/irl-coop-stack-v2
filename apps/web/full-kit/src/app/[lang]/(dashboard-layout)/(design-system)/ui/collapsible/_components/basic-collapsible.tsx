import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"

export function BasicCollapsible() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Basic Collapsible</CardTitle>
      </CardHeader>
      <CardContent className="flex justify-center items-center">
        <Collapsible>
          <CollapsibleTrigger>Learn more about our services</CollapsibleTrigger>
          <CollapsibleContent>
            Our services include web development, mobile app development, and
            cloud solutions tailored to your needs.
          </CollapsibleContent>
        </Collapsible>
      </CardContent>
    </Card>
  )
}
