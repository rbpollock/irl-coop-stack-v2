import { useParams } from "next/navigation"
import { redirect } from "next/navigation"

/**
 * Redirect from the old /docs/design/<slug> route to /docs/<slug>.
 * The design docs have been consolidated under /docs directly.
 */
export default function OldDesignDocRedirect() {
  const params = useParams<{ slug: string }>()
  redirect(`/docs/${params.slug}`)
}