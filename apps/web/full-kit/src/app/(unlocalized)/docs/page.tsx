import { redirect } from "next/navigation"

export default function DocsPage() {
  // Redirect to the localized inbox page
  redirect("/docs/overview/introduction")
}
