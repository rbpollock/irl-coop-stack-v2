import type { Metadata } from "next"

import { BasicEditor } from "./_components/basic-editor"
import { EditorBubbleMenu } from "./_components/editor-bubble-menu"
import { EditorPlaceholder } from "./_components/editor-placeholder"

// Define metadata for the page
// More info: https://nextjs.org/docs/app/building-your-application/optimizing/metadata
export const metadata: Metadata = {
  title: "Editor",
}

export default function EditorPage() {
  return (
    <section className="container grid gap-4 p-4 md:grid-cols-2">
      <BasicEditor />
      <EditorPlaceholder />
      <EditorBubbleMenu />
    </section>
  )
}
