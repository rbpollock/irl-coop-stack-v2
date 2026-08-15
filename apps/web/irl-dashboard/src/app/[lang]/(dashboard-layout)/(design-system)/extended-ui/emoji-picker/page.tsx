import type { Metadata } from "next"

import { BasicEmojiPicker } from "./_components/basic-emoji-picker"
import { ReactionPickerComponent } from "./_components/reaction-picker"

// Define metadata for the page
// More info: https://nextjs.org/docs/app/building-your-application/optimizing/metadata
export const metadata: Metadata = {
  title: "Emoji Picker",
}

export default function EmojiPickerPage() {
  return (
    <section className="container grid gap-4 p-4 md:grid-cols-2">
      <BasicEmojiPicker />
      <ReactionPickerComponent />
    </section>
  )
}
