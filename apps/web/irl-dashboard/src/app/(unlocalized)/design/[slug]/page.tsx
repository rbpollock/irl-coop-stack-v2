import { redirect } from "next/navigation"
import { notFound } from "next/navigation"

/**
 * Redirect from /design/<slug> to /docs/design/<slug>
 * The design docs have been consolidated under the /docs route
 * with the full docs layout (sidebar, breadcrumb, pagination, toc).
 *
 * This redirect preserves existing links and bookmarks.
 */

export default async function DesignRedirectPage({
  params,
}: {
  params: Promise<{ slug: string }>
}) {
  const { slug } = await params
  // Preserve the slug in the new URL
  redirect(`/docs/design/${slug}`)
}