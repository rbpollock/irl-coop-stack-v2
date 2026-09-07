import type { LocaleType } from "@/types"
import type { ReactNode } from "react"

import { getDictionary } from "@/lib/get-dictionary"

import { OnboardingGuard } from "@/components/auth/onboarding-guard"
import { Layout } from "@/components/layout"
import { AssistantPanel } from "@/components/layout/assistant-panel"
import { ChatWidget } from "@/components/layout/chat-widget"

export default async function DashboardLayout(props: {
  children: ReactNode
  params: Promise<{ lang: LocaleType }>
}) {
  const params = await props.params

  const { children } = props

  const dictionary = await getDictionary(params.lang)

  return (
    <>
      <OnboardingGuard />
      <Layout dictionary={dictionary}>{children}</Layout>
      <AssistantPanel />
      <ChatWidget dictionary={dictionary} />
    </>
  )
}
