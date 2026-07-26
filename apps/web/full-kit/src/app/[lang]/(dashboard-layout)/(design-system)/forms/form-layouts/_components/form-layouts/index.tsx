"use client"

import { HorizontalFormLayout } from "./horizontal-form-layout"
import { VerticalFormLayout } from "./vertical-form-layout"

export function FormLayouts() {
  return (
    <section className="container grid gap-4 p-4">
      <VerticalFormLayout />
      <HorizontalFormLayout />
    </section>
  )
}
