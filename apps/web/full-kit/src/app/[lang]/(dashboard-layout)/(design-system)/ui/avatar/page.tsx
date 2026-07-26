import type { Metadata } from "next"

import { BasicAvatar } from "./_components/basic-avatar"

// Define metadata for the page
// More info: https://nextjs.org/docs/app/building-your-application/optimizing/metadata
export const metadata: Metadata = {
  title: "Avatar",
}

export default function AvatarPage() {
  return (
    <section className="container grid gap-4 p-4">
      <BasicAvatar />
    </section>
  )
}
