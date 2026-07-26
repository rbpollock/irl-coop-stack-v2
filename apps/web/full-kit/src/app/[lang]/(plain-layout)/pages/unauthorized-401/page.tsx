import type { LocaleType } from "@/types"

import { Unauthorized401 } from "@/components/pages/unauthorized-401"

export default async function Unauthorized401Pgae(props: {
  params: Promise<{ lang: LocaleType }>
}) {
  const params = await props.params
  return <Unauthorized401 locale={params.lang} />
}
