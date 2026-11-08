import { redirect } from "next/navigation"

/**
 * Redirect from /docs/design to /docs
 * Design docs are now served directly at /docs/<slug>
 */
export default function OldDesignIndexRedirect() {
  redirect("/docs")
}