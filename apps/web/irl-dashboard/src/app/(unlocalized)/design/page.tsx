import { redirect } from "next/navigation"

/**
 * Redirect from /design to /docs/design
 * The design docs have been consolidated under the /docs route
 * with the full docs layout (sidebar, breadcrumb, pagination, toc).
 */

export default function DesignIndexRedirect() {
  redirect("/docs/design")
}