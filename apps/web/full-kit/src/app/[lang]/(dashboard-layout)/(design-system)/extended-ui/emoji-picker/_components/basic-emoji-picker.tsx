import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { EmojiPicker } from "@/components/ui/emoji-picker"

export function BasicEmojiPicker() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Basic Emoji Picker</CardTitle>
      </CardHeader>
      <CardContent className="flex items-center justify-center">
        <EmojiPicker popoverContentOptions={{ align: "center" }} />
      </CardContent>
    </Card>
  )
}
