import { redirect } from "next/navigation"

export default function DocsPage() {
  // Redirect to the design docs index - design docs now serve at /docs/design
  redirect("/docs/design")
}
