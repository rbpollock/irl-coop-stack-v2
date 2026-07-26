import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { ReactionPicker } from "@/components/ui/emoji-picker"

export function ReactionPickerComponent() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Reaction Picker</CardTitle>
      </CardHeader>
      <CardContent className="flex items-center justify-center">
        <ReactionPicker popoverContentOptions={{ align: "center" }} />
      </CardContent>
    </Card>
  )
}
