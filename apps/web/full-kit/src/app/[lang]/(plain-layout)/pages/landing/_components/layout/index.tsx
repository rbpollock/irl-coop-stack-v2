import type { DictionaryType } from "@/lib/get-dictionary"
import type { ReactNode } from "react"

import { LandingFooter } from "./landing-footer"
import { LandingHeader } from "./landing-header"

export function Layout({
  children,
  dictionary,
}: {
  children: ReactNode
  dictionary: DictionaryType
}) {
  return (
    <div className="grow">
      <LandingHeader dictionary={dictionary} />
      <main>{children}</main>
      <LandingFooter />
    </div>
  )
}
